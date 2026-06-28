"""Notifier protocol — swap out Telegram for another backend easily."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Notifier(Protocol):
    async def send_message(self, text: str, photo_url: str | None = None) -> None:
        """Send a text message, optionally with a photo."""
        ...
