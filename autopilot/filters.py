"""Cheap, deterministic filters that run BEFORE any paid LLM call."""

from __future__ import annotations

import datetime as dt
import re

from .models import Job


def _rx(patterns) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in patterns or []]


def _loc_rx(token: str) -> re.Pattern:
    """Whole-word match so 'india' never matches 'Indiana'."""
    t = re.escape(token.strip().lower())
    left = r"\b" if token[:1].isalnum() else ""
    right = r"\b" if token[-1:].isalnum() else ""
    return re.compile(left + t + right, re.I)


class Filters:
    def __init__(self, cfg: dict, today: dt.date | None = None):
        self.roles = {name: _rx(p) for name, p in cfg["roles"].items()}
        self.exclude = _rx(cfg.get("exclude_title"))
        self.countries = {cc: c for cc, c in cfg["countries"].items() if c.get("enabled")}
        self.loc = {cc: [_loc_rx(t) for t in c.get("locations", [])] for cc, c in self.countries.items()}
        self.days = int(cfg.get("posted_within_days", 7))
        self.today = today or dt.date.today()

    def role_of(self, title: str) -> str:
        if any(r.search(title) for r in self.exclude):
            return ""
        for name, pats in self.roles.items():
            if any(p.search(title) for p in pats):
                return name
        return ""

    def country_of(self, job: Job) -> str:
        if job.country in self.countries:      # Adzuna already knows
            return job.country
        loc = job.location or ""
        for cc, pats in self.loc.items():
            if any(p.search(loc) for p in pats):
                return cc
        code = (job.extra.get("country_code") or job.extra.get("country_name") or "").lower()
        for cc, names in (("us", ("us", "united states")), ("ca", ("ca", "canada")), ("in", ("in", "india"))):
            if cc in self.countries and code in names:
                return cc
        bare_remote = re.fullmatch(r"\s*(fully\s+)?remote\s*", loc, re.I)
        if bare_remote:
            for cc, c in self.countries.items():
                if c.get("accept_plain_remote"):
                    return cc
        return ""

    def is_recent(self, job: Job) -> bool:
        if not job.posted_at:
            return True  # unknown date: keep, the LLM step still filters
        try:
            d = dt.date.fromisoformat(job.posted_at[:10])
        except ValueError:
            return True
        return (self.today - d).days <= self.days

    def apply(self, jobs: list[Job]) -> list[Job]:
        kept, seen = [], set()
        for j in jobs:
            if not j.title:
                continue
            j.role = self.role_of(j.title)
            if not j.role:
                continue
            j.country = self.country_of(j)
            if not j.country or not self.is_recent(j):
                continue
            if j.key in seen:
                continue
            seen.add(j.key)
            kept.append(j)
        return kept
