"""Autopilot entry point.

    python -m autopilot.run                 # full run (dry_run from config)
    python -m autopilot.run --dry-run       # force: never click Submit
    python -m autopilot.run --discover-only # no LLM, no browser: list matching jobs
    python -m autopilot.run --check-boards  # which board tokens resolve
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path

from . import ats as ats_mod
from . import notify, scoring, sources, tailor
from .config import ConfigError, load_config, load_profile, work_auth_ready
from .filters import Filters
from .sources import adzuna
from .state import State

log = logging.getLogger("autopilot")
HERE = Path(__file__).resolve().parent


def _out_dir() -> Path:
    d = Path(os.environ.get("AUTOPILOT_OUT", HERE / "out")) / dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    d.mkdir(parents=True, exist_ok=True)
    return d


def discover(cfg: dict, state: State) -> tuple[list, dict]:
    raw, stats = sources.collect(cfg)
    jobs = [j for j in Filters(cfg).apply(raw) if not state.is_seen(j.key)]
    # ATS-hosted first (auto-applicable), then newest
    jobs.sort(key=lambda j: j.posted_at or "", reverse=True)
    jobs.sort(key=lambda j: j.ats == "")  # stable: keeps newest-first inside each group
    stats["raw"], stats["new_matching"] = len(raw), len(jobs)
    return jobs, stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="autopilot")
    ap.add_argument("--dry-run", action="store_true", help="never click Submit, whatever config says")
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--check-boards", action="store_true")
    ap.add_argument("--max-score", type=int, help="override max_jobs_scored_per_run")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    if a.check_boards:
        for k, v in sources.check_boards(cfg).items():
            print(f"{k:40s} {v}")
        return 0

    state = State()
    jobs, stats = discover(cfg, state)
    log.info("discovered %s new matching jobs (raw %s)", stats["new_matching"], stats["raw"])
    if a.discover_only:
        for j in jobs:
            print(f"[{j.country}] [{j.ats or j.source}] {j.company} — {j.title} — {j.location}\n    {j.url}")
        return 0

    try:
        profile = load_profile()
    except ConfigError as e:
        print(f"profile error: {e}", file=sys.stderr)
        return 2

    dry = a.dry_run or bool(cfg["dry_run"])
    out = _out_dir()
    budget = a.max_score or int(cfg["max_jobs_scored_per_run"])
    applied_live = 0
    report = {"dry_run": dry, "stats": stats, "applied": [], "manual": [], "skipped": 0, "errors": []}
    browser = context = pw = None

    try:
        for job in jobs[:budget]:
            try:
                fit = scoring.score(job, profile, cfg["model"])
            except Exception as e:
                report["errors"].append(f"score {job.company}/{job.title}: {e}")
                continue
            sc = fit["score"]
            state.mark_seen(job, score=sc)
            if fit.get("dealbreaker") or sc < cfg["manual_digest_min_score"]:
                report["skipped"] += 1
                continue
            entry = {"company": job.company, "title": job.title, "country": job.country, "url": job.url,
                     "score": sc, "summary": fit.get("summary", ""), "gaps": fit.get("gaps", [])}
            if sc < cfg["min_fit_score"]:
                report["manual"].append({**entry, "why": "below auto-apply score"})
                continue

            # Resolve where the form lives
            if job.source == "adzuna":
                real = adzuna.resolve_apply_url(job.url)
                job.ats, form = ats_mod.detect(real)
                if form:
                    job.apply_url = form
                else:
                    entry["url"] = real
            try:
                tailored, warnings = tailor.tailor(job, profile, cfg["model"], fit)
            except Exception as e:
                report["errors"].append(f"tailor {job.company}/{job.title}: {e}")
                continue
            from .documents import cover_letter_pdf, resume_pdf  # reportlab only when needed
            jdir = out / job.key
            c = profile["contact"]
            resume = resume_pdf(jdir / f"{c['first_name']}_{c['last_name']}_Resume.pdf", profile, tailored, job.country)
            cover = cover_letter_pdf(jdir / f"{c['first_name']}_{c['last_name']}_Cover_Letter.pdf", profile,
                                     tailored["cover_letter"], job.company, job.country)
            (jdir / "tailoring.json").write_text(json.dumps({"fit": fit, "tailored": tailored, "warnings": warnings,
                                                             "job": job.to_dict()}, indent=1), encoding="utf-8")
            entry["docs"] = str(jdir)

            why = None
            if job.ats not in ats_mod.SUPPORTED:
                why = "not on Greenhouse/Lever/Ashby — apply by hand"
            elif not work_auth_ready(profile, job.country):
                why = f"work_authorization.{job.country} not filled in profile"
            elif state.company_count(job.company) >= cfg["max_per_company_per_30d"]:
                why = "company cap reached (30 days)"
            elif applied_live >= cfg["max_applications_per_run"]:
                why = "run cap reached"
            if why:
                report["manual"].append({**entry, "why": why})
                state.record_application(job, "manual", [why], sc)
                continue

            if browser is None:
                from playwright.sync_api import sync_playwright
                pw = sync_playwright().start()
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 1600}, locale="en-US")
            from .apply.engine import apply_job
            res = apply_job(context, job=job, profile=profile, resume=resume, cover=cover,
                            letter=tailored["cover_letter"], dry_run=dry, shot_dir=out / "screens")
            state.record_application(job, res.status, res.reasons, sc)
            (jdir / "apply_result.json").write_text(json.dumps(res.__dict__, indent=1, default=str), encoding="utf-8")
            if res.status == "submitted":
                applied_live += 1
            if res.status in ("submitted", "dry_run"):
                report["applied"].append({**entry, "status": res.status})
            else:
                report["manual"].append({**entry, "why": "; ".join(res.reasons)[:300] or res.status})
    finally:
        if browser:
            browser.close()
        if pw:
            pw.stop()
        state.prune()
        state.save()

    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    text = summarize(report)
    (out / "report.md").write_text(text, encoding="utf-8")
    print(text)
    notify.send(text)
    return 0


def summarize(r: dict) -> str:
    mode = "DRY RUN (nothing submitted)" if r["dry_run"] else "LIVE"
    lines = [f"Job autopilot — {dt.date.today():%a %d %b} — {mode}",
             f"new matching: {r['stats'].get('new_matching')} | skipped low fit: {r['skipped']}", ""]
    done = [x for x in r["applied"] if x["status"] == "submitted"]
    ready = [x for x in r["applied"] if x["status"] == "dry_run"]
    if done:
        lines.append(f"✅ Applied ({len(done)}):")
        lines += [f"• [{x['country'].upper()}] {x['company']} — {x['title']} ({x['score']})" for x in done]
    if ready:
        lines.append(f"🧪 Filled, not submitted ({len(ready)}):")
        lines += [f"• [{x['country'].upper()}] {x['company']} — {x['title']} ({x['score']})" for x in ready]
    if r["manual"]:
        lines.append(f"\n👀 Needs you ({len(r['manual'])}):")
        for x in sorted(r["manual"], key=lambda x: -x["score"])[:25]:
            lines.append(f"• [{x['country'].upper()}] {x['company']} — {x['title']} ({x['score']})\n  {x['why']}\n  {x['url']}")
    if r["errors"]:
        lines.append(f"\n⚠️ errors: {len(r['errors'])} (see report.json)")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
