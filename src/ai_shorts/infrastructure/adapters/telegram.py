"""
Telegram Adapter — NotificationService implementation.

Sends pipeline notifications via Telegram Bot API.
Uses raw urllib to avoid external dependencies.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import TYPE_CHECKING

from ai_shorts.domain.ports import NotificationService

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)


class TelegramNotifier(NotificationService):
    """Sends notifications via Telegram Bot API.

    Uses urllib (no external dependencies) for maximum portability.
    Silently fails if not configured — notifications are non-critical.
    """

    def __init__(self, settings: Settings) -> None:
        self._token = settings.telegram.bot_token
        self._chat_id = settings.telegram.chat_id

    def send(self, message: str) -> bool:
        """Send a notification message via Telegram.

        Args:
            message: The message text (supports Telegram markdown).

        Returns:
            True if sent successfully.
        """
        if not self._token or not self._chat_id:
            log.info("ℹ️  Telegram not configured, skipping notification")
            return False

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": self._chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("ok"):
                    log.info("📨 Telegram notification sent")
                    return True
                else:
                    log.warning("⚠️  Telegram API error: %s", result)
                    return False
        except Exception as e:
            log.warning("⚠️  Telegram notification failed: %s", e)
            return False
