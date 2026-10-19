"""Job sources. Each module exposes parse(payload, token) (pure, tested) and fetch(token)."""

from __future__ import annotations

import logging

from . import adzuna, ashby, greenhouse, lever

log = logging.getLogger("autopilot.sources")

BOARD_MODULES = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def collect(cfg: dict) -> tuple[list, dict]:
    """Fetch every configured board + Adzuna. Returns (jobs, per-source stats)."""
    jobs, stats = [], {}
    for name, mod in BOARD_MODULES.items():
        for token in cfg.get("boards", {}).get(name, []) or []:
            try:
                got = mod.fetch(token)
                jobs.extend(got)
                stats[f"{name}:{token}"] = len(got)
            except Exception as e:  # one dead board must not kill the run
                stats[f"{name}:{token}"] = f"error: {e}"
                log.warning("board %s:%s failed: %s", name, token, e)
    if (cfg.get("adzuna") or {}).get("enabled"):
        got, err = adzuna.fetch_all(cfg)
        jobs.extend(got)
        stats["adzuna"] = err or len(got)
    return jobs, stats


def check_boards(cfg: dict) -> dict:
    out = {}
    for name, mod in BOARD_MODULES.items():
        for token in cfg.get("boards", {}).get(name, []) or []:
            try:
                out[f"{name}:{token}"] = f"ok ({len(mod.fetch(token))} jobs)"
            except Exception as e:
                out[f"{name}:{token}"] = f"FAIL {e}"
    return out
