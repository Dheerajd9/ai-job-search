"""Shared data model: one normalized job posting, whatever board it came from."""

from __future__ import annotations

import html
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from job_key import make_key  # noqa: E402  (reuse the repo's canonical dedup key)


@dataclass
class Job:
    source: str            # greenhouse | lever | ashby | adzuna
    source_id: str
    company: str
    title: str
    location: str
    url: str               # posting page
    apply_url: str         # where the form lives (may equal url)
    description: str = ""  # plain text
    posted_at: str = ""    # ISO date if known
    country: str = ""      # us | ca | in, set by filters
    role: str = ""         # matched role bucket, set by filters
    ats: str = ""          # greenhouse | lever | ashby | "" (unsupported)
    salary: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return make_key(self.company, self.title, self.url)

    def to_dict(self) -> dict:
        return asdict(self)


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")


def html_to_text(raw: str) -> str:
    """Board APIs return HTML (Greenhouse double-escapes it). Good-enough text for an LLM."""
    if not raw:
        return ""
    text = html.unescape(html.unescape(raw))
    text = re.sub(r"(?i)<\s*(br|/p|/li|/h\d|/div)\s*/?>", "\n", text)
    text = re.sub(r"(?i)<\s*li[^>]*>", "- ", text)
    text = _TAG.sub("", text)
    text = _WS.sub(" ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
