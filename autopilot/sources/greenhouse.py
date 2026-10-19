"""Greenhouse public Job Board API: boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true"""

from __future__ import annotations

from ..models import Job, html_to_text
from ..net import get_json

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def parse(payload: dict, token: str) -> list[Job]:
    company = (payload.get("meta") or {}).get("company_name") or token
    out = []
    for j in payload.get("jobs", []) or []:
        jid = str(j.get("id", ""))
        if not jid:
            continue
        loc = (j.get("location") or {}).get("name", "") or ", ".join(
            o.get("name", "") for o in j.get("offices", []) or [])
        apply_url = f"https://job-boards.greenhouse.io/{token}/jobs/{jid}"
        out.append(Job(
            source="greenhouse", source_id=jid, company=j.get("company_name") or company,
            title=(j.get("title") or "").strip(), location=loc,
            url=j.get("absolute_url") or apply_url, apply_url=apply_url,
            description=html_to_text(j.get("content", "")),
            posted_at=(j.get("first_published") or j.get("updated_at") or "")[:10],
            ats="greenhouse", extra={"board": token},
        ))
    return out


def fetch(token: str) -> list[Job]:
    return parse(get_json(API.format(token=token)), token)
