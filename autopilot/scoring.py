"""LLM fit scoring — one call per job, strict JSON out."""

from __future__ import annotations

from . import llm, profile_text
from .models import Job

SYSTEM = f"""You are a strict technical hiring manager screening candidates for data, AI and
infrastructure roles in the US, Canada and India. Score how well the candidate fits the job,
honestly — an inflated score wastes everyone's time. {llm.UNTRUSTED_NOTE}

Reply with ONLY a JSON object:
{{"score": 0-100,
  "seniority_fit": "under|match|over",
  "strengths": ["max 4 short items"],
  "gaps": ["max 4 short items"],
  "dealbreaker": null or "short reason (e.g. requires security clearance, requires a
                 citizenship/visa status the candidate lacks, requires 10+ years, onsite in a
                 city the candidate cannot work in, language the candidate lacks)",
  "summary": "one sentence"}}

Scoring guide: 85+ = would interview immediately; 70-84 = solid match with gaps;
50-69 = stretch; <50 = wrong role. Score against MUST-HAVE requirements first."""


def score(job: Job, profile: dict, model: str) -> dict:
    wa = (profile.get("work_authorization") or {}).get(job.country) or {}
    user = (f"CANDIDATE PROFILE\n{profile_text.render(profile)}\n"
            f"Work authorization in this job's country ({job.country.upper()}): "
            f"authorized={wa.get('authorized')}, needs_sponsorship={wa.get('needs_sponsorship')}\n\n"
            f"JOB ({job.source})\nTitle: {job.title}\nCompany: {job.company}\nLocation: {job.location}\n"
            f"Salary: {job.salary or 'n/a'}\n<posting>\n{job.description[:9000]}\n</posting>")
    out = llm.extract_json(llm.complete(SYSTEM, user, model=model, max_tokens=800))
    try:
        out["score"] = max(0, min(100, int(out.get("score", 0))))
    except (TypeError, ValueError):
        out["score"] = 0
    return out
