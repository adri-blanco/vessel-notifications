"""
Telegram notifier using python-telegram-bot (async).

Sends HTML messages to a configured chat/channel.
Optionally attaches a photo when photo_url is provided.
"""

from __future__ import annotations

import logging

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

_MAX_CAPTION_LEN = 1024
_MAX_TEXT_LEN = 4096


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self._bot = Bot(token=token)
        self._chat_id = chat_id

    async def send_message(self, text: str, photo_url: str | None = None) -> None:
        try:
            if photo_url:
                await self._send_with_photo(text, photo_url)
            else:
                await self._send_text(text)
        except TelegramError as exc:
            logger.error("Telegram send failed: %s", exc)

    async def _send_text(self, text: str) -> None:
        # Truncate if needed
        if len(text) > _MAX_TEXT_LEN:
            text = text[:_MAX_TEXT_LEN - 3] + "..."
        await self._bot.send_message(
            chat_id=self._chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    async def _send_with_photo(self, text: str, photo_url: str) -> None:
        # Telegram captions have a smaller limit than plain text
        if len(text) > _MAX_CAPTION_LEN:
            caption = text[:_MAX_CAPTION_LEN - 3] + "..."
        else:
            caption = text
        try:
            await self._bot.send_photo(
                chat_id=self._chat_id,
                photo=photo_url,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            # Fall back to text if photo fails (e.g. bad URL, 403 from Wikimedia)
            logger.warning("Photo send failed, falling back to text-only")
            await self._send_text(text)
