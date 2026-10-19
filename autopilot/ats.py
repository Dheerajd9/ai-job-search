"""Recognise which applicant-tracking system hosts a posting, and its form URL."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_GH = re.compile(r"^(?:job-)?boards(?:\.eu)?\.greenhouse\.io$")
_GH_PATH = re.compile(r"^/(?:embed/job_app)?/?([A-Za-z0-9_-]+)/jobs/(\d+)")
_LEVER_PATH = re.compile(r"^/([A-Za-z0-9_.-]+)/([0-9a-f-]{36})")
_ASHBY_PATH = re.compile(r"^/([A-Za-z0-9_.%-]+)/([0-9a-f-]{36})")

SUPPORTED = ("greenhouse", "lever", "ashby")


def detect(url: str) -> tuple[str, str | None]:
    """Return (ats, canonical_apply_url) or ("", None) when unsupported."""
    if not url:
        return "", None
    u = urlparse(url)
    host = (u.hostname or "").lower()
    if _GH.match(host):
        m = _GH_PATH.match(u.path)
        if m:
            return "greenhouse", f"https://job-boards.greenhouse.io/{m.group(1)}/jobs/{m.group(2)}"
        q = parse_qs(u.query)
        if "for" in q and "token" in q:  # embed form
            return "greenhouse", f"https://job-boards.greenhouse.io/{q['for'][0]}/jobs/{q['token'][0]}"
    if host == "jobs.lever.co" or host == "jobs.eu.lever.co":
        m = _LEVER_PATH.match(u.path)
        if m:
            return "lever", f"https://{host}/{m.group(1)}/{m.group(2)}/apply"
    if host == "jobs.ashbyhq.com":
        m = _ASHBY_PATH.match(u.path)
        if m:
            return "ashby", f"https://jobs.ashbyhq.com/{m.group(1)}/{m.group(2)}/application"
    return "", None
