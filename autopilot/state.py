"""Persistent run state: which jobs were already scored / applied. JSON, one file."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

DEFAULT = Path(os.environ.get("AUTOPILOT_STATE", Path(__file__).resolve().parent / "state" / "state.json"))


class State:
    def __init__(self, path: Path = DEFAULT):
        self.path = Path(path)
        data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.seen: dict = data.get("seen", {})
        self.applications: list = data.get("applications", [])

    def is_seen(self, key: str) -> bool:
        return key in self.seen

    def mark_seen(self, job, score=None, status="scored", **extra) -> None:
        self.seen[job.key] = {"date": dt.date.today().isoformat(), "company": job.company,
                              "title": job.title, "url": job.url, "score": score, "status": status, **extra}

    def company_count(self, company: str, days: int = 30, today: dt.date | None = None) -> int:
        today = today or dt.date.today()
        c = company.strip().lower()
        n = 0
        for a in self.applications:
            if a.get("status") == "submitted" and a.get("company", "").strip().lower() == c:
                if (today - dt.date.fromisoformat(a["date"])).days <= days:
                    n += 1
        return n

    def record_application(self, job, status: str, reasons=None, score=None) -> None:
        self.applications.append({"date": dt.date.today().isoformat(), "key": job.key, "company": job.company,
                                  "title": job.title, "url": job.url, "country": job.country,
                                  "ats": job.ats, "status": status, "score": score, "reasons": reasons or []})
        if job.key in self.seen:
            self.seen[job.key]["status"] = status

    def prune(self, keep_days: int = 120) -> None:
        cutoff = (dt.date.today() - dt.timedelta(days=keep_days)).isoformat()
        self.seen = {k: v for k, v in self.seen.items() if v.get("date", "9") >= cutoff}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"seen": self.seen, "applications": self.applications}, indent=1), encoding="utf-8")
        tmp.replace(self.path)
