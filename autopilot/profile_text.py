"""Render profile.yaml as compact text for prompts."""

from __future__ import annotations


def render(profile: dict, include_ids: bool = False) -> str:
    c = profile.get("contact", {})
    lines = [f"Candidate: {c.get('first_name', '')} {c.get('last_name', '')} — {c.get('city', '')}, "
             f"{c.get('region', '')}, {c.get('country', '')}",
             f"Headline: {profile.get('headline', '')}",
             f"Skills: {', '.join(profile.get('skills', []))}"]
    for cert in profile.get("certifications", []) or []:
        lines.append(f"Certification: {cert.get('name')} ({cert.get('issuer', '')}, {cert.get('date', '')})")
    for e in profile.get("education", []) or []:
        lines.append(f"Education: {e.get('degree')} — {e.get('school')} ({e.get('start', '')}–{e.get('end', '')})")
    for job in profile.get("experience", []):
        tag = f"[{job['id']}] " if include_ids else ""
        lines.append(f"\n{tag}{job.get('title')} — {job.get('company')} ({job.get('location', '')}) "
                     f"{job.get('start', '')}–{job.get('end', '')}")
        for b in job.get("bullets", []):
            lines.append(f"  - {'[' + b['id'] + '] ' if include_ids else ''}{b['text']}")
    lines.append(f"\nRelocation: {'yes' if profile.get('willing_to_relocate') else 'no'}; "
                 f"availability: {profile.get('notice_period', '')}")
    return "\n".join(lines)
