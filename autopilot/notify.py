"""Telegram run summary (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID). Silently skipped if unset."""

from __future__ import annotations

import logging
import os

from .net import post_json

log = logging.getLogger("autopilot.notify")


def send(text: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    ok = True
    for i in range(0, len(text), 3900):
        try:
            post_json(f"https://api.telegram.org/bot{token}/sendMessage",
                      {"chat_id": chat, "text": text[i:i + 3900], "disable_web_page_preview": True}, timeout=30)
        except Exception as e:
            log.warning("telegram send failed: %s", e)
            ok = False
    return ok
