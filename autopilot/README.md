# Job Autopilot — US · Canada · India

Daily, unattended pipeline that sits next to the interactive `/scrape` → `/apply` workflow:

```
Greenhouse / Lever / Ashby boards ─┐
Adzuna (US, CA, IN)  ──────────────┼─► role + country + date filters ─► Claude fit score
                                   │      (free, no LLM)                 (strict, JSON)
                                   │
          score ≥ min_fit_score ───┴─► tailored resume + cover letter (only YOUR facts)
                                        │
             on Greenhouse/Lever/Ashby ─┼─► Playwright fills the form ─► submit ─► confirmation check
             anything else / blocked ───┴─► "Needs you" digest (Telegram + report)
```

Roles out of the box: Data Engineer, Data Analyst, Data Center, AI Engineer,
Forward Deployed Engineer, MLOps (edit `roles:` in `config.yaml`).

## Safety rails (why you can let it run)

| Rail | Behaviour |
|---|---|
| `dry_run: true` (default) | Fills every form + screenshots, never clicks Submit |
| Work authorization | Never guessed. Country with `null` values in `profile.yaml` → no submits there |
| Unknown required question | Job goes to "Needs you", nothing submitted |
| CAPTCHA / email code / login wall | Stops, goes to "Needs you". Never bypassed |
| Honesty | LLM only selects/orders your bullets + skills; summary/letter with any number not in your profile is rejected |
| Spam caps | `max_applications_per_run`, `max_per_company_per_30d`, every job applied at most once |
| Prompt injection | Postings are passed as untrusted data, never as instructions |
| Privacy | Workflow refuses to run in a public repo; profile only via secret; state on an orphan branch |
| Voluntary EEO questions | Always "decline to answer" |

Not automated on purpose: LinkedIn Easy Apply, Naukri, Indeed, Workday — login-walled and/or
their terms forbid bots, and accounts get banned. Those land in the digest with a tailored resume ready.

## Setup (≈20 min)

1. **Private repo.** A GitHub fork is always public. Create a private copy and push this branch:
   ```bash
   gh repo create ai-job-search-private --private
   git remote add private https://github.com/<you>/ai-job-search-private.git
   git push private autopilot-us-ca-in:master
   ```
2. **Profile.** `cp autopilot/profile.example.yaml autopilot/profile.yaml`, fill it in (real titles,
   6–8 strong bullets per job, `work_authorization` for each country). It is gitignored.
3. **Config.** Optional: `cp autopilot/config.example.yaml autopilot/config.yaml` and edit roles,
   locations, board list. Commit it (no personal data inside).
4. **Secrets** (private repo → Settings → Secrets → Actions):

   | Secret | Where from |
   |---|---|
   | `ANTHROPIC_API_KEY` | console.anthropic.com |
   | `AUTOPILOT_PROFILE_B64` | `base64 -w0 autopilot/profile.yaml` (macOS: `base64 -i autopilot/profile.yaml`) |
   | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | developer.adzuna.com (free) — optional |
   | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | your existing bot — optional |
5. **First run:** Actions → *Job autopilot* → Run workflow (dry run ticked). Download the artifact,
   look at `screens/*.png` and the PDFs.
6. **Go live:** set `dry_run: false` in `config.yaml`, commit. The cron runs daily 08:47 New York.

## Local use

```bash
pip install -r autopilot/requirements.txt && python -m playwright install chromium
python -m autopilot.run --check-boards     # which board tokens exist
python -m autopilot.run --discover-only    # matching jobs, no LLM, no browser
python -m autopilot.run --dry-run          # full pipeline, never submits
python -m unittest discover -s autopilot/tests -t .
```

Output per run: `autopilot/out/<timestamp>/` — `report.md`, `report.json`, one folder per job
(resume PDF, cover letter PDF, `tailoring.json`, `apply_result.json`) and `screens/`.

## Cost

Scoring ≈ 1 short call per new matching job, tailoring 1 call per job above `min_fit_score`.
`max_jobs_scored_per_run: 60` keeps a day well under a dollar or two on Sonnet.

## Extending

* More companies: add board tokens under `boards:` (slug from `job-boards.greenhouse.io/<slug>`,
  `jobs.lever.co/<slug>`, `jobs.ashbyhq.com/<slug>`), then `--check-boards`.
* New screening answers: add `match`/`answer` pairs under `answers:` in `profile.yaml` — the
  "Needs you" digest tells you exactly which question labels were unanswered.
