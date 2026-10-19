"""Lever public Postings API: api.lever.co/v0/postings/<company>?mode=json"""

from __future__ import annotations

import datetime as dt

from ..models import Job, html_to_text
from ..net import get_json

API = "https://api.lever.co/v0/postings/{token}?mode=json"


def parse(payload: list, token: str) -> list[Job]:
    out = []
    for p in payload or []:
        pid = p.get("id")
        if not pid:
            continue
        cats = p.get("categories") or {}
        locs = cats.get("allLocations") or [cats.get("location", "")]
        loc = " / ".join(x for x in locs if x)
        if p.get("workplaceType") == "remote" and "remote" not in loc.lower():
            loc = f"Remote - {loc}" if loc else "Remote"
        desc = p.get("descriptionPlain") or html_to_text(p.get("description", ""))
        for lst in p.get("lists", []) or []:
            desc += f"\n\n{lst.get('text', '')}\n{html_to_text(lst.get('content', ''))}"
        desc += "\n\n" + (p.get("additionalPlain") or "")
        created = p.get("createdAt")
        posted = dt.datetime.fromtimestamp(created / 1000, dt.timezone.utc).date().isoformat() if created else ""
        hosted = p.get("hostedUrl") or f"https://jobs.lever.co/{token}/{pid}"
        out.append(Job(
            source="lever", source_id=pid, company=token.replace("-", " ").title(),
            title=(p.get("text") or "").strip(), location=loc, url=hosted,
            apply_url=p.get("applyUrl") or f"{hosted}/apply", description=desc.strip(),
            posted_at=posted, ats="lever",
            extra={"board": token, "country_code": (p.get("country") or "").lower()},
        ))
    return out


def fetch(token: str) -> list[Job]:
    return parse(get_json(API.format(token=token)), token)
