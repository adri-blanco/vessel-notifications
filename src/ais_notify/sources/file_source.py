"""File source — replays a .nmea file for offline testing without hardware."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator

from ais_notify.sources.base import AISSource

logger = logging.getLogger(__name__)

_DEFAULT_LINE_DELAY = 0.05  # seconds between lines to avoid flooding


class FileSource(AISSource):
    """
    Reads NMEA sentences from a local file.

    With loop=True the file will be re-read from the beginning after EOF,
    useful for continuous integration / smoke testing.
    """

    def __init__(
        self,
        path: str | Path,
        loop: bool = False,
        line_delay: float = _DEFAULT_LINE_DELAY,
    ) -> None:
        self._path = Path(path)
        self._loop = loop
        self._line_delay = line_delay

    @property
    def name(self) -> str:
        return f"file:{self._path.name}"

    async def iter_sentences(self) -> AsyncIterator[bytes]:
        while True:
            if not self._path.exists():
                raise FileNotFoundError(f"NMEA file not found: {self._path}")

            logger.info("File source reading %s (loop=%s)", self._path, self._loop)
            with self._path.open("rb") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if line and not line.startswith(b"#"):
                        yield line
                    if self._line_delay:
                        await asyncio.sleep(self._line_delay)

            if not self._loop:
                logger.info("File source reached EOF: %s", self._path)
                return
            logger.debug("File source looping back to start: %s", self._path)
