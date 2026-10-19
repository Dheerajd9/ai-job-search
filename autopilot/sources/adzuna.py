"""Adzuna search API (US / CA / IN). Needs ADZUNA_APP_ID + ADZUNA_APP_KEY (free tier).

Adzuna is discovery only: its redirect_url lands on Adzuna, so the runner resolves
the real apply page later (resolve_apply_url) and only auto-applies when that page
is Greenhouse / Lever / Ashby.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlencode

from ..models import Job, html_to_text
from ..net import get_json, request

log = logging.getLogger("autopilot.adzuna")
API = "https://api.adzuna.com/v1/api/jobs/{cc}/search/1?{qs}"

# One search phrase per role bucket — keeps the API call count small.
ROLE_QUERIES = {
    "data_engineer": "data engineer",
    "data_analyst": "data analyst",
    "data_center": "data center",
    "ai_engineer": "ai engineer",
    "forward_deployed": "forward deployed engineer",
    "mlops": "mlops engineer",
}


def parse(payload: dict, cc: str) -> list[Job]:
    out = []
    for r in payload.get("results", []) or []:
        rid = str(r.get("id", ""))
        if not rid:
            continue
        sal = ""
        if r.get("salary_min"):
            sal = f"{int(r['salary_min'])}-{int(r.get('salary_max') or r['salary_min'])}"
            if str(r.get("salary_is_predicted")) == "1":
                sal += " (estimated)"
        url = r.get("redirect_url", "")
        out.append(Job(
            source="adzuna", source_id=rid,
            company=((r.get("company") or {}).get("display_name") or "").strip(),
            title=html_to_text(r.get("title", "")), location=(r.get("location") or {}).get("display_name", ""),
            url=url, apply_url=url, description=html_to_text(r.get("description", "")),
            posted_at=(r.get("created") or "")[:10], country=cc, salary=sal,
            extra={"adzuna_country": cc},
        ))
    return out


def fetch_all(cfg: dict) -> tuple[list[Job], str]:
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        return [], "skipped (no ADZUNA_APP_ID/ADZUNA_APP_KEY)"
    per = int((cfg.get("adzuna") or {}).get("results_per_query", 50))
    days = int(cfg.get("posted_within_days", 7))
    roles = [r for r in cfg["roles"] if r in ROLE_QUERIES]
    jobs: list[Job] = []
    for cc, ccfg in cfg["countries"].items():
        if not ccfg.get("enabled"):
            continue
        for where in ccfg.get("adzuna_where", []) or [""]:
            for role in roles:
                qs = urlencode({"app_id": app_id, "app_key": app_key, "what": ROLE_QUERIES[role],
                                "where": where, "results_per_page": per, "max_days_old": days,
                                "content-type": "application/json"})
                try:
                    jobs.extend(parse(get_json(API.format(cc=cc, qs=qs)), cc))
                except Exception as e:
                    log.warning("adzuna %s/%s/%s failed: %s", cc, where, role, e)
    return jobs, ""


def resolve_apply_url(url: str) -> str:
    """Follow Adzuna's redirect chain to the employer's page (one GET, no form interaction)."""
    try:
        _, _, final = request(url, headers={"Accept": "text/html"}, retries=1, timeout=20)
        return final
    except Exception:
        return url
