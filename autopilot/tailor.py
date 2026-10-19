"""Tailor resume + cover letter WITHOUT inventing anything.

The model never writes resume bullets. It only:
  * picks + orders bullet IDs that already exist in profile.yaml,
  * picks skills from the profile's skill list,
  * writes a <=60-word summary and a short cover letter.
Both free-text parts go through a fact guard: any number that does not appear
in the profile (e.g. an invented "40%" or "8 years") rejects the text.
"""

from __future__ import annotations

import json
import re

from . import llm, profile_text
from .models import Job

SYSTEM = f"""You tailor a resume and cover letter for one job. You may ONLY use facts from the
candidate profile. Never invent employers, titles, dates, metrics, tools or achievements.
{llm.UNTRUSTED_NOTE}

Reply with ONLY a JSON object:
{{"summary": "2-3 sentences, max 60 words, first person implied (no 'I')",
  "skills": ["12-20 skills copied EXACTLY from the profile skill list, most relevant first"],
  "bullets": {{"<experience id>": ["<bullet id>", ...]}},   // every experience id; 3-6 most relevant bullet ids each, best first
  "cover_letter": "150-230 words, plain text, 3 short paragraphs, no greeting/sign-off lines"}}"""

_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(text)}


def fact_guard(text: str, allowed_source: str) -> list[str]:
    """Return numbers in `text` that never occur in the allowed source text."""
    return sorted(_numbers(text) - _numbers(allowed_source))


def validate(raw: dict, profile: dict, job: Job) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    source = profile_text.render(profile) + "\n" + json.dumps(profile.get("answers", [])) + f"\n{job.title} {job.company}"

    known = {s.lower(): s for s in profile.get("skills", [])}
    skills = [known[s.lower()] for s in raw.get("skills", []) if isinstance(s, str) and s.lower() in known]
    dropped = [s for s in raw.get("skills", []) if not (isinstance(s, str) and s.lower() in known)]
    if dropped:
        warnings.append(f"dropped non-profile skills: {dropped}")
    if len(skills) < 5:
        skills = list(profile.get("skills", []))[:20]

    bullets: dict[str, list[str]] = {}
    for exp in profile["experience"]:
        valid = {b["id"] for b in exp.get("bullets", [])}
        picked = [b for b in (raw.get("bullets") or {}).get(exp["id"], []) if b in valid]
        bullets[exp["id"]] = list(dict.fromkeys(picked)) or [b["id"] for b in exp.get("bullets", [])][:5]

    summary = str(raw.get("summary", "")).strip()
    bad = fact_guard(summary, source)
    if bad or not summary or len(summary.split()) > 80:
        warnings.append(f"summary rejected (unverified numbers {bad})" if bad else "summary rejected (length)")
        summary = profile.get("headline", "")

    letter = str(raw.get("cover_letter", "")).strip()
    bad = fact_guard(letter, source)
    if bad:
        warnings.append(f"cover letter rejected: unverified numbers {bad}")
        letter = ""
    return {"summary": summary, "skills": skills, "bullets": bullets, "cover_letter": letter}, warnings


def tailor(job: Job, profile: dict, model: str, fit: dict | None = None) -> tuple[dict, list[str]]:
    user = (f"CANDIDATE PROFILE (ids in brackets)\n{profile_text.render(profile, include_ids=True)}\n\n"
            f"JOB\nTitle: {job.title}\nCompany: {job.company}\nLocation: {job.location} ({job.country.upper()})\n"
            f"Screening notes: {json.dumps(fit or {})[:600]}\n<posting>\n{job.description[:9000]}\n</posting>")
    raw = llm.extract_json(llm.complete(SYSTEM, user, model=model, max_tokens=2000))
    return validate(raw, profile, job)
