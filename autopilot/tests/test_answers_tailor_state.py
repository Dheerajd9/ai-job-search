import datetime as dt
import tempfile
import unittest
from pathlib import Path

from autopilot.answers import answer_for, pick_option
from autopilot.config import work_auth_ready
from autopilot.models import Job
from autopilot.state import State
from autopilot.tailor import fact_guard, validate

from .helpers import profile


def job(country="us", company="Acme"):
    return Job(source="greenhouse", source_id="1", company=company, title="Data Engineer", location="Remote",
               url="https://boards.greenhouse.io/acme/jobs/1", apply_url="", country=country)


class TestAnswers(unittest.TestCase):
    def test_legal_questions(self):
        p = profile()
        self.assertEqual(answer_for("Are you legally authorized to work in the US?", p, "us"), "Yes")
        self.assertEqual(answer_for("Will you now or in the future require visa sponsorship?", p, "us"), "No")
        self.assertEqual(answer_for("Are you authorized to work in the US without sponsorship?", p, "us"), "Yes")
        # unanswered country -> never guessed
        self.assertIsNone(answer_for("Do you require sponsorship?", p, "ca"))
        self.assertFalse(work_auth_ready(p, "ca"))
        self.assertTrue(work_auth_ready(p, "us"))
        # free-text legal question is never answered with a bare Yes/No
        self.assertIsNone(answer_for("What is your current visa status?", p, "us", choice=False))

    def test_without_sponsorship_when_sponsorship_needed(self):
        p = profile(work_authorization={"us": {"authorized": True, "needs_sponsorship": True}})
        self.assertEqual(answer_for("Can you work in the US without employer sponsorship?", p, "us"), "No")

    def test_eeo_and_consent(self):
        p = profile()
        self.assertEqual(answer_for("Gender", p, "us"), "__DECLINE__")
        self.assertEqual(pick_option("__DECLINE__", ["Male", "Female", "I don't wish to answer"]), "I don't wish to answer")
        self.assertIsNone(answer_for("I acknowledge the privacy notice", p, "us"))
        p2 = profile(accept_application_privacy_consent=True)
        self.assertEqual(answer_for("I acknowledge the privacy notice", p2, "us"), "__CONSENT__")

    def test_basics_and_custom(self):
        p = profile()
        self.assertEqual(answer_for("First Name*", p, "us"), "Test")
        self.assertEqual(answer_for("Full name ✱", p, "us"), "Test Person")
        self.assertEqual(answer_for("How did you hear about this job?*", p, "us"), "Company careers page")
        self.assertIsNone(answer_for("Describe a hard bug you fixed*", p, "us"))
        self.assertIsNone(answer_for("Desired salary", p, "us"))          # empty -> human decides

    def test_pick_option(self):
        self.assertEqual(pick_option("Yes", ["Select...", "Yes", "No"]), "Yes")
        self.assertEqual(pick_option("No", ["Yes, I will", "No, I will not"]), "No, I will not")
        self.assertIsNone(pick_option("Yes", ["Select..."]))


class TestTailorGuard(unittest.TestCase):
    def test_fact_guard(self):
        src = "Built pipelines processing 2 TB daily, cutting runtime by 35%."
        self.assertEqual(fact_guard("Cut runtime 35% on 2 TB/day.", src), [])
        self.assertEqual(fact_guard("Saved $3M and led 12 engineers.", src), ["12", "3"])

    def test_validate_strips_inventions(self):
        raw = {"summary": "Data engineer with 9 years of Spark.",
               "skills": ["Python", "PySpark", "Rust", "SQL", "Databricks", "Kafka", "Azure"],
               "bullets": {"j1": ["j1-b", "j1-zzz", "j1-a"], "j2": []},
               "cover_letter": "I processed 2 TB daily and cut runtime by 35% at Bank Co."}
        out, warns = validate(raw, profile(), job())
        self.assertNotIn("Rust", out["skills"])
        self.assertEqual(out["bullets"]["j1"], ["j1-b", "j1-a"])
        self.assertEqual(out["bullets"]["j2"], ["j2-a"])
        self.assertEqual(out["summary"], "Data / MLOps Engineer")     # '9' not in profile
        self.assertIn("35%", out["cover_letter"])
        self.assertTrue(any("summary rejected" in w for w in warns))


class TestState(unittest.TestCase):
    def test_company_cap_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            s = State(Path(d) / "s.json")
            j = job()
            s.mark_seen(j, score=80)
            s.record_application(j, "submitted")
            s.record_application(job(company="acme "), "submitted")
            s.record_application(job(company="Other"), "needs_human")
            s.save()
            s2 = State(Path(d) / "s.json")
            self.assertTrue(s2.is_seen(j.key))
            self.assertEqual(s2.company_count("ACME"), 2)
            self.assertEqual(s2.company_count("Other"), 0)
            self.assertEqual(s2.company_count("Acme", today=dt.date.today() + dt.timedelta(days=40)), 0)


if __name__ == "__main__":
    unittest.main()


class TestConfigFiles(unittest.TestCase):
    def test_example_config_is_valid(self):
        from autopilot.config import HERE, load_config
        cfg = load_config(HERE / "config.example.yaml")
        self.assertTrue(cfg["dry_run"])
        self.assertEqual(set(cfg["countries"]), {"us", "ca", "in"})

    def test_placeholders_block_profile(self):
        from autopilot.config import HERE, ConfigError, load_profile
        with self.assertRaises(ConfigError):
            load_profile(HERE / "profile.example.yaml")
        import yaml
        with tempfile.TemporaryDirectory() as d:
            p = profile()
            p["experience"][0]["bullets"][0]["text"] = "[bullet]"
            path = Path(d) / "p.yaml"
            path.write_text(yaml.safe_dump(p))
            with self.assertRaisesRegex(ConfigError, "placeholders"):
                load_profile(path)
            path.write_text(yaml.safe_dump(profile()))
            self.assertEqual(load_profile(path)["contact"]["first_name"], "Test")
