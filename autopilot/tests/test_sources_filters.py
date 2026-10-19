import datetime as dt
import unittest

from autopilot import ats
from autopilot.filters import Filters
from autopilot.sources import adzuna, ashby, greenhouse, lever

from .helpers import CFG, load

TODAY = dt.date(2026, 10, 18)


class TestParsers(unittest.TestCase):
    def test_greenhouse(self):
        jobs = greenhouse.parse(load("greenhouse.json"), "acme")
        self.assertEqual(len(jobs), 4)
        j = jobs[0]
        self.assertEqual(j.apply_url, "https://job-boards.greenhouse.io/acme/jobs/7001")
        self.assertEqual(j.company, "Acme Data")
        self.assertIn("Spark", j.description)
        self.assertIn("- Python", j.description)
        self.assertNotIn("<", j.description)
        self.assertEqual(j.posted_at, "2026-10-16")

    def test_lever(self):
        jobs = lever.parse(load("lever.json"), "wealthy")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].location, "Toronto, ON / Vancouver, BC")
        self.assertIn("Kubernetes", jobs[0].description)
        self.assertTrue(jobs[1].apply_url.endswith("/apply"))
        self.assertEqual(jobs[1].location, "Remote")

    def test_ashby_skips_unlisted(self):
        jobs = ashby.parse(load("ashby.json"), "aicorp")
        self.assertEqual(len(jobs), 1)
        self.assertIn("Hyderabad", jobs[0].location)
        self.assertEqual(jobs[0].salary, "₹40L – ₹60L")

    def test_adzuna(self):
        jobs = adzuna.parse(load("adzuna.json"), "us")
        self.assertEqual(jobs[0].title, "Data Center Technician")
        self.assertEqual(jobs[0].salary, "60000-75000")
        self.assertEqual(jobs[0].country, "us")


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.f = Filters(CFG, today=TODAY)

    def test_roles_and_excludes(self):
        self.assertEqual(self.f.role_of("Senior Data Engineer"), "data_engineer")
        self.assertEqual(self.f.role_of("Data Engineering Manager"), "")
        self.assertEqual(self.f.role_of("Data Analyst Intern"), "")
        self.assertEqual(self.f.role_of("Forward-Deployed Engineer, AI"), "forward_deployed")
        self.assertEqual(self.f.role_of("Account Executive"), "")

    def test_end_to_end(self):
        raw = (greenhouse.parse(load("greenhouse.json"), "acme") + lever.parse(load("lever.json"), "wealthy")
               + ashby.parse(load("ashby.json"), "aicorp") + adzuna.parse(load("adzuna.json"), "us"))
        kept = {(j.title, j.country) for j in self.f.apply(raw)}
        self.assertIn(("Senior Data Engineer", "us"), kept)
        self.assertIn(("MLOps Engineer", "ca"), kept)
        self.assertIn(("Forward Deployed Engineer", "us"), kept)    # bare Remote -> US
        self.assertIn(("AI Engineer", "in"), kept)
        self.assertIn(("Data Center Technician", "us"), kept)
        self.assertNotIn(("Data Engineer II", "in"), kept)           # Indiana is not India
        self.assertEqual(len(kept), 5)

    def test_old_postings_dropped(self):
        jobs = greenhouse.parse(load("greenhouse.json"), "acme")
        jobs[0].posted_at = "2026-09-01"
        self.assertFalse(self.f.is_recent(jobs[0]))


class TestAts(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(ats.detect("https://boards.greenhouse.io/stripe/jobs/123?gh_src=x"),
                         ("greenhouse", "https://job-boards.greenhouse.io/stripe/jobs/123"))
        self.assertEqual(ats.detect("https://jobs.lever.co/plaid/3f1c2a4b-1111-2222-3333-444455556666")[0], "lever")
        self.assertTrue(ats.detect("https://jobs.ashbyhq.com/openai/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")[1]
                        .endswith("/application"))
        self.assertEqual(ats.detect("https://www.naukri.com/job-listings-123"), ("", None))
        self.assertEqual(ats.detect("https://evilgreenhouse.io/x/jobs/1"), ("", None))


if __name__ == "__main__":
    unittest.main()
