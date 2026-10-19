"""Map an application-form question to an answer from profile.yaml — or None.

None on a REQUIRED question means "a human must look": the job goes to the
manual digest. Nothing here ever guesses a legal answer (work authorization,
sponsorship): those come only from profile.work_authorization.
"""

from __future__ import annotations

import re

DECLINE = re.compile(r"decline|prefer not|don.?t wish|do not wish|not to (answer|disclose|say)|i don.?t want|rather not", re.I)

# (pattern, resolver-name). Order matters: legal first.
_LEGAL = [
    (re.compile(r"sponsor|visa|h-?1b|immigration", re.I), "sponsorship"),
    (re.compile(r"(legally )?(authori[sz]ed|eligible|permitted|right) to work|work authori[sz]ation|work permit", re.I), "authorized"),
]
_EEO = re.compile(r"\b(gender|sex\b|race|ethnic|hispanic|latin[oa]|veteran|disabilit|sexual orientation|transgender|lgbt)", re.I)
_BUILTIN = [
    (re.compile(r"first name|given name", re.I), lambda p, c: p["contact"]["first_name"]),
    (re.compile(r"last name|surname|family name", re.I), lambda p, c: p["contact"]["last_name"]),
    (re.compile(r"^\s*(full )?name\s*\*?$|full legal name|your name", re.I),
     lambda p, c: f"{p['contact']['first_name']} {p['contact']['last_name']}"),
    (re.compile(r"e-?mail", re.I), lambda p, c: p["contact"]["email"]),
    (re.compile(r"phone|mobile", re.I), lambda p, c: p["contact"]["phone"]),
    (re.compile(r"linkedin", re.I), lambda p, c: p["contact"].get("linkedin") or None),
    (re.compile(r"github", re.I), lambda p, c: p["contact"].get("github") or None),
    (re.compile(r"website|portfolio|personal (site|url)", re.I),
     lambda p, c: p["contact"].get("portfolio") or p["contact"].get("github") or p["contact"].get("linkedin") or None),
    (re.compile(r"current (company|employer)|^org(anization)?$", re.I), lambda p, c: p["contact"].get("current_company") or None),
    (re.compile(r"relocat", re.I), lambda p, c: "Yes" if p.get("willing_to_relocate") else "No"),
    (re.compile(r"salary|compensation|pay expectation|expected (ctc|pay)|\bctc\b", re.I),
     lambda p, c: (p.get("salary_expectation") or {}).get(c) or None),
    (re.compile(r"notice period|start date|when can you (start|join)|available to start|availability", re.I),
     lambda p, c: p.get("notice_period") or None),
    (re.compile(r"pronoun", re.I), lambda p, c: p.get("pronouns") or "__DECLINE__"),
    (re.compile(r"(current|your) (city|location)|where are you (located|based)|^location", re.I),
     lambda p, c: ", ".join(x for x in (p["contact"].get("city"), p["contact"].get("region")) if x) or None),
    (re.compile(r"^\s*city\s*\*?$", re.I), lambda p, c: p["contact"].get("city") or None),
    (re.compile(r"^\s*(state|province|region)\s*\*?$", re.I), lambda p, c: p["contact"].get("region") or None),
    (re.compile(r"^\s*country\s*\*?$|country of residence", re.I), lambda p, c: p["contact"].get("country") or None),
]
CONSENT = re.compile(r"consent|acknowledg|privacy (policy|notice)|i agree|i certify|i confirm|data (processing|retention)", re.I)


def _yn(v: bool) -> str:
    return "Yes" if v else "No"


_WITHOUT_SPONSOR = re.compile(r"without (the )?(need (for|of) )?(any |employer |visa )?sponsor", re.I)


def answer_for(label: str, profile: dict, country: str, choice: bool = True) -> str | None:
    """Text answer for a question label, '__DECLINE__' for voluntary EEO, or None.

    choice=False means a free-text box: legal questions there ("what is your visa
    status?") are never auto-answered with a bare Yes/No.
    """
    text = re.sub(r"\s*(\(required\)|[*✱])+\s*$", "", (label or "").strip())
    if not text:
        return None
    for item in profile.get("answers", []) or []:   # the user's explicit answers win
        if re.search(item["match"], text, re.I):
            return str(item["answer"])
    wa = (profile.get("work_authorization") or {}).get(country) or {}
    auth, needs = wa.get("authorized"), wa.get("needs_sponsorship")
    if _WITHOUT_SPONSOR.search(text):
        # "Are you authorized to work ... without sponsorship?" -> yes only if both hold
        if not choice or not isinstance(auth, bool) or not isinstance(needs, bool):
            return None
        return _yn(auth and not needs)
    for rx, kind in _LEGAL:
        if rx.search(text):
            v = needs if kind == "sponsorship" else auth
            return _yn(v) if (choice and isinstance(v, bool)) else None
    if _EEO.search(text) and profile.get("eeo_policy", "decline") == "decline":
        return "__DECLINE__"
    if CONSENT.search(text):
        return "__CONSENT__" if profile.get("accept_application_privacy_consent") else None
    for rx, fn in _BUILTIN:
        if rx.search(text):
            return fn(profile, country)
    return None


def pick_option(answer: str, options: list[str]) -> str | None:
    """Choose the option that best matches an answer. None if nothing fits."""
    opts = [o for o in options if o and o.strip() and not re.fullmatch(r"\s*(select|choose|--).*", o, re.I)]
    if not opts:
        return None
    if answer == "__DECLINE__":
        return next((o for o in opts if DECLINE.search(o)), None)
    if answer == "__CONSENT__":
        return next((o for o in opts if re.match(r"\s*(yes|i agree|i acknowledge|i consent|agree)", o, re.I)), None)
    a = answer.strip().lower()
    for o in opts:
        if o.strip().lower() == a:
            return o
    if a in ("yes", "no"):
        for o in opts:
            if re.match(rf"\s*{a}\b", o, re.I):
                return o
        return None
    for o in opts:
        if o.strip().lower().startswith(a) or a.startswith(o.strip().lower()):
            return o
    for o in opts:
        if a in o.lower():
            return o
    return None
