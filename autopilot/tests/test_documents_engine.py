import tempfile
import unittest
from pathlib import Path

from autopilot.models import Job

from .helpers import FIX, profile

try:
    import reportlab  # noqa: F401
    HAVE_RL = True
except ImportError:
    HAVE_RL = False

try:
    from playwright.sync_api import sync_playwright
    _p = sync_playwright().start()
    _b = _p.chromium.launch()
    _b.close()
    _p.stop()
    HAVE_PW = True
except Exception:
    HAVE_PW = False

TAILORED = {"summary": "Data engineer focused on Spark and Azure.", "skills": ["Python", "PySpark", "SQL"],
            "bullets": {"j1": ["j1-a", "j1-b"], "j2": ["j2-a"]},
            "cover_letter": "Para one.\n\nPara two about PySpark.\n\nPara three."}


@unittest.skipUnless(HAVE_RL, "reportlab not installed")
class TestDocuments(unittest.TestCase):
    def test_pdfs_have_text(self):
        from autopilot.documents import cover_letter_pdf, resume_pdf
        with tempfile.TemporaryDirectory() as d:
            r = resume_pdf(Path(d) / "r.pdf", profile(), TAILORED, "us")
            c = cover_letter_pdf(Path(d) / "c.pdf", profile(), TAILORED["cover_letter"], "Acme", "in")
            self.assertGreater(r.stat().st_size, 1000)
            self.assertGreater(c.stat().st_size, 500)
            self.assertIsNone(cover_letter_pdf(Path(d) / "x.pdf", profile(), "", "Acme", "us"))
            try:
                from pypdf import PdfReader
            except ImportError:
                return
            text = "".join(p.extract_text() for p in PdfReader(str(r)).pages)
            self.assertIn("Test Person", text)
            self.assertIn("test@example.com", text)
            self.assertIn("2 TB daily", text)
            self.assertNotIn("Great Expectations", text)   # j1-c not selected


def _job(country="us"):
    return Job(source="greenhouse", source_id="1", company="Acme", title="Data Engineer", location="Remote",
               url="x", apply_url="", country=country)


@unittest.skipUnless(HAVE_PW and HAVE_RL, "playwright chromium not available")
class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from autopilot.documents import resume_pdf
        cls.tmp = tempfile.TemporaryDirectory()
        cls.resume = resume_pdf(Path(cls.tmp.name) / "resume.pdf", profile(), TAILORED, "us")
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def run_form(self, name, *, dry_run, prof=None, country="us"):
        from autopilot.apply.engine import apply_job
        job = _job(country)
        job.apply_url = (FIX / name).as_uri()
        ctx = self.browser.new_context()
        try:
            return apply_job(ctx, job=job, profile=prof or profile(), resume=self.resume, cover=None,
                             letter="", dry_run=dry_run, shot_dir=Path(self.tmp.name) / "shots")
        finally:
            ctx.close()

    def test_greenhouse_dry_run_fills_everything(self):
        res = self.run_form("gh_form.html", dry_run=True)
        self.assertEqual(res.status, "dry_run", res.reasons)
        filled = dict(res.filled)
        self.assertEqual(filled["First Name*"], "Test")
        self.assertEqual(filled["Will you now or in the future require sponsorship for employment visa status?*"], "No")
        self.assertEqual(filled["How did you hear about this job?*"], "Company careers page")
        self.assertEqual(filled["Gender"], "I don't wish to answer")
        self.assertEqual(filled["Veteran Status"], "Decline to self identify")
        self.assertTrue(Path(res.screenshot).exists())

    def test_greenhouse_submit_detects_confirmation(self):
        res = self.run_form("gh_form.html", dry_run=False)
        self.assertEqual(res.status, "submitted", res.reasons)

    def test_lever_unknown_required_goes_to_human(self):
        p = profile(answers=[])            # no answer for the Kubeflow question
        res = self.run_form("lever_form.html", dry_run=False, prof=p)
        self.assertEqual(res.status, "needs_human")
        self.assertTrue(any("Kubeflow" in r for r in res.reasons), res.reasons)

    def test_lever_with_answer_submits(self):
        res = self.run_form("lever_form.html", dry_run=False)
        self.assertEqual(res.status, "submitted", res.reasons)
        self.assertEqual(dict(res.filled)["Full name ✱"], "Test Person")

    def test_ashby_consent_blocks_unless_allowed(self):
        res = self.run_form("ashby_form.html", dry_run=True, country="in")
        self.assertEqual(res.status, "needs_human")
        self.assertTrue(any("acknowledge" in r.lower() for r in res.reasons), res.reasons)
        res = self.run_form("ashby_form.html", dry_run=False, country="in",
                            prof=profile(accept_application_privacy_consent=True))
        self.assertEqual(res.status, "submitted", res.reasons)


if __name__ == "__main__":
    unittest.main()
