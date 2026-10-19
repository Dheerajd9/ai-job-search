"""Ashby public Job Posting API: api.ashbyhq.com/posting-api/job-board/<name>?includeCompensation=true"""

from __future__ import annotations

from ..models import Job, html_to_text
from ..net import get_json

API = "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"


def parse(payload: dict, token: str) -> list[Job]:
    out = []
    for j in payload.get("jobs", []) or []:
        if j.get("isListed") is False:
            continue
        jid = j.get("id")
        if not jid:
            continue
        locs = [j.get("location") or ""] + [
            (s.get("location") if isinstance(s, dict) else str(s)) for s in j.get("secondaryLocations") or []]
        loc = " / ".join(x for x in locs if x)
        if j.get("isRemote") and "remote" not in loc.lower():
            loc = f"Remote - {loc}" if loc else "Remote"
        addr = ((j.get("address") or {}).get("postalAddress") or {})
        url = j.get("jobUrl") or f"https://jobs.ashbyhq.com/{token}/{jid}"
        comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
        out.append(Job(
            source="ashby", source_id=jid, company=token.replace("-", " ").title(),
            title=(j.get("title") or "").strip(), location=loc, url=url,
            apply_url=j.get("applyUrl") or f"{url}/application",
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")),
            posted_at=(j.get("publishedAt") or "")[:10], ats="ashby", salary=comp,
            extra={"board": token, "country_name": addr.get("addressCountry", "")},
        ))
    return out


def fetch(token: str) -> list[Job]:
    return parse(get_json(API.format(token=token)), token)
