"""End-to-end run with the network + LLM mocked out and a local Greenhouse-like form."""

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from autopilot import run
from autopilot.sources import greenhouse
from autopilot.state import State as RealState

from .helpers import CFG, FIX, load, profile
from .test_documents_engine import HAVE_PW, HAVE_RL


def fake_score(job, prof, model):
    return {"score": 90 if "Senior" in job.title else 70, "summary": "ok", "gaps": [], "dealbreaker": None}


def fake_tailor(job, prof, model, fit=None):
    return ({"summary": "Data engineer.", "skills": ["Python", "SQL"], "bullets": {"j1": ["j1-a"], "j2": ["j2-a"]},
             "cover_letter": "Short letter."}, [])


@unittest.skipUnless(HAVE_PW and HAVE_RL, "needs playwright chromium + reportlab")
class TestPipeline(unittest.TestCase):
    def test_full_run(self):
        jobs = greenhouse.parse(load("greenhouse.json"), "acme")
        for j in jobs:
            j.apply_url = (FIX / "gh_form.html").as_uri()
            j.posted_at = ""   # keep regardless of today's date
        cfg = {**CFG, "dry_run": False, "min_fit_score": 75, "manual_digest_min_score": 65,
               "max_jobs_scored_per_run": 10, "max_applications_per_run": 5, "max_per_company_per_30d": 2,
               "model": "x", "boards": {}}
        with tempfile.TemporaryDirectory() as d:
            env = {"AUTOPILOT_CONFIG_B64": base64.b64encode(yaml.safe_dump(cfg).encode()).decode(),
                   "AUTOPILOT_PROFILE_B64": base64.b64encode(yaml.safe_dump(profile()).encode()).decode(),
                   "AUTOPILOT_OUT": d}
            state_path = Path(d) / "state.json"
            with mock.patch.dict(os.environ, env), \
                 mock.patch("autopilot.sources.collect", return_value=(jobs, {})), \
                 mock.patch("autopilot.scoring.score", side_effect=fake_score), \
                 mock.patch("autopilot.tailor.tailor", side_effect=fake_tailor), \
                 mock.patch("autopilot.run.State", side_effect=lambda: RealState(state_path)), \
                 mock.patch("autopilot.notify.send", return_value=False):
                self.assertEqual(run.main([]), 0)
                report = json.loads(next(Path(d).glob("*/report.json")).read_text())
                self.assertEqual([a["status"] for a in report["applied"]], ["submitted"])
                self.assertEqual(report["applied"][0]["title"], "Senior Data Engineer")
                self.assertEqual(len(report["manual"]), 0)
                # second run: everything already seen -> nothing new, nothing re-applied
                self.assertEqual(run.main([]), 0)
                state = json.loads(state_path.read_text())
                self.assertEqual(sum(a["status"] == "submitted" for a in state["applications"]), 1)


if __name__ == "__main__":
    unittest.main()
