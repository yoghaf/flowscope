from __future__ import annotations

import html
import logging

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(timeout=15.0)

    @property
    def configured(self) -> bool:
        return bool(self.settings.telegram_alerts_enabled and self.settings.telegram_bot_token)

    async def close(self) -> None:
        await self._client.aclose()

    async def send_message(self, chat_id: str, text: str) -> tuple[bool, str]:
        if not self.configured:
            return False, "Telegram bot token is not configured on the server."

        token = self.settings.telegram_bot_token
        if token is None:
            return False, "Telegram bot token is missing."

        try:
            response = await self._client.post(
                f"{self.settings.telegram_api_base.rstrip('/')}/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                description = payload.get("description", "Unknown Telegram API error.")
                return False, str(description)
            return True, "Telegram message sent."
        except Exception as exc:  # pragma: no cover - network failure path
            logger.warning("Telegram send failed chat_id=%s error=%s", chat_id, exc)
            return False, str(exc)

    @staticmethod
    def escape(value: str) -> str:
        return html.escape(value, quote=False)
