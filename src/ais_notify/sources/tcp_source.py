"""TCP source — connects to a NMEA TCP server (e.g. SignalK, AIS-catcher --server)."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from ais_notify.sources.base import AISSource

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 5.0  # seconds


class TCPSource(AISSource):
    """Opens a persistent TCP connection and reads NMEA lines."""

    def __init__(self, host: str = "127.0.0.1", port: int = 10110) -> None:
        self._host = host
        self._port = port

    @property
    def name(self) -> str:
        return f"tcp:{self._host}:{self._port}"

    async def iter_sentences(self) -> AsyncIterator[bytes]:
        while True:
            try:
                reader, writer = await asyncio.open_connection(self._host, self._port)
                logger.info("TCP source connected to %s:%d", self._host, self._port)
                try:
                    async for line in reader:
                        line = line.strip()
                        if line:
                            yield line
                finally:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                logger.warning("TCP source connection closed, reconnecting in %ss", _RECONNECT_DELAY)
            except (OSError, asyncio.IncompleteReadError) as exc:
                logger.warning("TCP source error (%s), retrying in %ss", exc, _RECONNECT_DELAY)
            await asyncio.sleep(_RECONNECT_DELAY)
