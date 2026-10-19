"""Generic ATS form filler (Playwright). One code path for Greenhouse, Lever and Ashby.

Safety contract:
  * every REQUIRED field must get an answer from profile.yaml, else -> needs_human
  * CAPTCHA / email security code / login wall -> needs_human (never bypassed)
  * dry_run fills + screenshots but never clicks Submit
  * submit counts as success only when a confirmation is detected
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..answers import answer_for, pick_option

log = logging.getLogger("autopilot.apply")
SCAN_JS = (Path(__file__).parent / "scan.js").read_text(encoding="utf-8")

CHOICE_KINDS = {"select", "radio", "checkbox-group", "buttons", "combobox", "checkbox"}
RESUME = re.compile(r"resume|\bcv\b|curriculum", re.I)
COVER = re.compile(r"cover letter|covering letter|motivation", re.I)
ADDITIONAL = re.compile(r"additional information|anything else|comments", re.I)

BLOCKERS = [
    (re.compile(r"security code|verification code (was|has been) sent|enter the code", re.I), "email security code required"),
    (re.compile(r"sign in to apply|log in to apply|create an account to apply", re.I), "login required"),
    (re.compile(r"no longer accepting|position has been filled|job (is )?(no longer|not) available|page not found", re.I), "posting closed"),
]
SUCCESS = re.compile(r"thank(s| you) for (applying|your (application|interest))|application (has been |was )?(received|submitted)|we('ve| have) received your application|successfully submitted", re.I)
CAPTCHA_FRAMES = ("hcaptcha.com", "recaptcha/api2/bframe", "recaptcha/enterprise/bframe", "challenges.cloudflare.com")


@dataclass
class ApplyResult:
    status: str                       # submitted | dry_run | needs_human | error
    reasons: list = field(default_factory=list)
    filled: list = field(default_factory=list)
    screenshot: str = ""


def _visible_captcha(page) -> bool:
    for fr in page.frames:
        if any(s in (fr.url or "") for s in CAPTCHA_FRAMES):
            try:
                el = fr.frame_element()
                box = el.bounding_box()
                if box and box["width"] > 100 and box["height"] > 100 and el.is_visible():
                    return True
            except Exception:
                continue
    return False


def _body_text(page) -> str:
    try:
        return page.inner_text("body", timeout=5000)
    except Exception:
        return ""


def _open_form(page, ats: str) -> None:
    """Some boards show the description first and the form behind an Apply button."""
    if page.locator("input[type=file]").count() > 0:
        return
    for name in (r"^apply( for this job| now)?$", r"^application$", r"^i'?m interested$"):
        btn = page.get_by_role("button", name=re.compile(name, re.I))
        if btn.count() == 0:
            btn = page.get_by_role("link", name=re.compile(name, re.I))
        if btn.count() > 0:
            try:
                btn.first.click(timeout=5000)
                page.wait_for_timeout(1500)
                return
            except Exception:
                continue


def _choose_combobox(page, loc, answer: str) -> str | None:
    loc.click()
    if answer not in ("__DECLINE__", "__CONSENT__") and answer.lower() not in ("yes", "no"):
        loc.fill(answer[:40])
    page.wait_for_timeout(800)
    opts = page.locator("[role=option]")
    texts = [t.strip() for t in opts.all_inner_texts()]
    choice = pick_option(answer, texts)
    if choice is None:
        page.keyboard.press("Escape")
        return None
    opts.nth(texts.index(choice)).click()
    return choice


def fill_form(page, *, job, profile: dict, resume: Path, cover: Path | None, letter: str) -> ApplyResult:
    res = ApplyResult(status="needs_human")
    fields = page.evaluate(SCAN_JS)
    if not fields:
        res.reasons.append("no form fields found")
        return res
    resume_done = False
    for f in fields:
        label, kind, req = f["label"], f["kind"], f["required"]
        sel = f'[data-ap-id="{f["id"]}"]'
        loc = page.locator(sel).first
        try:
            if kind == "file":
                if RESUME.search(label) or (not resume_done and not COVER.search(label)):
                    loc.set_input_files(str(resume))
                    resume_done = True
                    res.filled.append((label or "resume", resume.name))
                    page.wait_for_timeout(1500)   # Lever/Greenhouse parse the upload
                elif COVER.search(label) and cover:
                    loc.set_input_files(str(cover))
                    res.filled.append((label, cover.name))
                elif req:
                    res.reasons.append(f"required upload with no file: {label!r}")
                continue
            if kind in ("textarea", "text") and COVER.search(label):
                if letter:
                    loc.fill(letter)
                    res.filled.append((label, "cover letter text"))
                elif req:
                    res.reasons.append("cover letter text required but none passed the fact guard")
                continue
            if kind == "textarea" and ADDITIONAL.search(label) and not req:
                continue
            ans = answer_for(label, profile, job.country, choice=kind in CHOICE_KINDS)
            if ans is None:
                if req:
                    res.reasons.append(f"no answer for required question: {label!r}")
                continue
            if kind in ("text", "email", "tel", "url", "number", "textarea"):
                if ans.startswith("__"):
                    if req:
                        res.reasons.append(f"cannot decline free-text field: {label!r}")
                    continue
                loc.fill(ans)
            elif kind == "select":
                choice = pick_option(ans, f["options"])
                if choice is None:
                    if req:
                        res.reasons.append(f"no matching option for {label!r} (answer {ans!r})")
                    continue
                loc.select_option(label=choice)
                ans = choice
            elif kind == "combobox":
                choice = _choose_combobox(page, loc, ans)
                if choice is None:
                    if req:
                        res.reasons.append(f"no matching option for {label!r} (answer {ans!r})")
                    continue
                ans = choice
            elif kind in ("radio", "checkbox-group", "buttons"):
                choice = pick_option(ans, f["options"])
                if choice is None:
                    if req:
                        res.reasons.append(f"no matching option for {label!r} (answer {ans!r})")
                    continue
                idx = f["options"].index(choice)
                if kind == "buttons":
                    loc.locator(f'[data-ap-opt="{idx}"]').click()
                else:
                    page.locator(f'[data-ap-group="{f["id"]}"][data-ap-opt="{idx}"]').check(force=True)
                ans = choice
            elif kind == "checkbox":
                if ans == "__CONSENT__" or ans.lower() == "yes":
                    loc.check(force=True)
                elif req:
                    res.reasons.append(f"required checkbox not auto-ticked: {label!r}")
                    continue
            else:
                if req:
                    res.reasons.append(f"unsupported field type {kind} for {label!r}")
                continue
            res.filled.append((label, ans))
        except Exception as e:
            if req:
                res.reasons.append(f"failed to fill {label!r}: {type(e).__name__}: {str(e)[:120]}")
    if not resume_done:
        res.reasons.append("no resume upload field found")
    if not res.reasons:
        res.status = "ready"
    return res


def apply_job(context, *, job, profile, resume: Path, cover: Path | None, letter: str,
              dry_run: bool, shot_dir: Path) -> ApplyResult:
    page = context.new_page()
    shot = shot_dir / f"{job.key}.png"
    shot_dir.mkdir(parents=True, exist_ok=True)
    try:
        page.goto(job.apply_url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        _open_form(page, job.ats)
        text = _body_text(page)
        for rx, why in BLOCKERS:
            if rx.search(text):
                page.screenshot(path=str(shot), full_page=True)
                return ApplyResult("needs_human", [why], screenshot=str(shot))
        if _visible_captcha(page):
            page.screenshot(path=str(shot), full_page=True)
            return ApplyResult("needs_human", ["captcha shown before submit"], screenshot=str(shot))

        res = fill_form(page, job=job, profile=profile, resume=resume, cover=cover, letter=letter)
        page.screenshot(path=str(shot), full_page=True)
        res.screenshot = str(shot)
        if res.status != "ready":
            return res
        if dry_run:
            res.status = "dry_run"
            return res

        submit = page.get_by_role("button", name=re.compile(r"^\s*submit( application| your application)?\s*$", re.I))
        if submit.count() == 0:
            submit = page.locator("button[type=submit], input[type=submit]")
        if submit.count() == 0:
            return ApplyResult("needs_human", ["submit button not found"], res.filled, str(shot))
        pre_text = _body_text(page).lower()
        start_url = page.url
        submit.first.click(timeout=10000)
        deadline = time.time() + 25
        while time.time() < deadline:
            page.wait_for_timeout(1500)
            moved = page.url != start_url and re.search(r"confirm|thank|success", page.url, re.I)
            # success = a confirmation phrase that was NOT already on the form page
            fresh = any(m.group(0).lower() not in pre_text for m in SUCCESS.finditer(_body_text(page)))
            if moved or fresh:
                page.screenshot(path=str(shot), full_page=True)
                return ApplyResult("submitted", [], res.filled, str(shot))
            if _visible_captcha(page):
                page.screenshot(path=str(shot), full_page=True)
                return ApplyResult("needs_human", ["captcha challenge on submit"], res.filled, str(shot))
            for rx, why in BLOCKERS[:1]:
                if rx.search(_body_text(page)):
                    page.screenshot(path=str(shot), full_page=True)
                    return ApplyResult("needs_human", [why + " after submit"], res.filled, str(shot))
        page.screenshot(path=str(shot), full_page=True)
        errs = page.locator("[class*=error], [role=alert]").all_inner_texts()
        return ApplyResult("error", ["no confirmation after submit"] + [e.strip()[:120] for e in errs if e.strip()][:3],
                           res.filled, str(shot))
    except Exception as e:
        try:
            page.screenshot(path=str(shot), full_page=True)
        except Exception:
            pass
        return ApplyResult("error", [f"{type(e).__name__}: {str(e)[:200]}"], screenshot=str(shot))
    finally:
        page.close()
