"""Load + validate config.yaml and profile.yaml."""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
COUNTRIES = ("us", "ca", "in")


class ConfigError(ValueError):
    pass


def _load_yaml(path: Path, env_b64: str | None = None) -> dict:
    if env_b64 and os.environ.get(env_b64):
        return yaml.safe_load(base64.b64decode(os.environ[env_b64]).decode("utf-8")) or {}
    if not path.exists():
        raise ConfigError(f"missing {path} (copy {path.stem}.example.yaml)")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(path: Path | None = None) -> dict:
    path = path or HERE / "config.yaml"
    if not path.exists() and not os.environ.get("AUTOPILOT_CONFIG_B64"):
        path = HERE / "config.example.yaml"
    cfg = _load_yaml(path, "AUTOPILOT_CONFIG_B64")
    for k in ("roles", "countries", "boards"):
        if k not in cfg:
            raise ConfigError(f"config missing '{k}'")
    for role, pats in cfg["roles"].items():
        for p in pats:
            re.compile(p)
    for p in cfg.get("exclude_title", []):
        re.compile(p)
    cfg.setdefault("dry_run", True)
    cfg.setdefault("min_fit_score", 75)
    cfg.setdefault("manual_digest_min_score", 65)
    cfg.setdefault("max_jobs_scored_per_run", 60)
    cfg.setdefault("max_applications_per_run", 15)
    cfg.setdefault("max_per_company_per_30d", 2)
    cfg.setdefault("posted_within_days", 7)
    cfg.setdefault("model", "claude-sonnet-5-5")
    return cfg


_PLACEHOLDER = re.compile(r"^\[.*\]$")


def load_profile(path: Path | None = None) -> dict:
    prof = _load_yaml(path or HERE / "profile.yaml", "AUTOPILOT_PROFILE_B64")
    c = prof.get("contact") or {}
    missing = [k for k in ("first_name", "last_name", "email", "phone")
               if not c.get(k) or _PLACEHOLDER.match(str(c.get(k)))]
    if missing:
        raise ConfigError(f"profile.contact missing/placeholder: {', '.join(missing)}")
    if not prof.get("experience"):
        raise ConfigError("profile.experience is empty")
    left = sorted(set(_placeholders(prof)))
    if left:
        raise ConfigError("profile still has placeholders (nothing will be sent until fixed): " + "; ".join(left[:8]))
    ids = set()
    for job in prof["experience"]:
        for b in job.get("bullets", []):
            if b["id"] in ids:
                raise ConfigError(f"duplicate bullet id {b['id']}")
            ids.add(b["id"])
    return prof


_BRACKET = re.compile(r"\[[A-Za-z][^\]]*\]")


def _placeholders(obj, path="profile"):
    """Yield paths of any '[FILL ME]'-style values left in the profile."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _placeholders(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _placeholders(v, f"{path}[{i}]")
    elif isinstance(obj, str) and _BRACKET.search(obj) and not path.endswith(".match"):
        yield f"{path}={obj[:40]!r}"


def work_auth_ready(profile: dict, country: str) -> bool:
    """Submit only where the user has explicitly answered both legal questions."""
    wa = (profile.get("work_authorization") or {}).get(country) or {}
    return isinstance(wa.get("authorized"), bool) and isinstance(wa.get("needs_sponsorship"), bool)
