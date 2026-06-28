"""UDP source — receives NMEA sentences from rtl-ais or AIS-catcher over UDP."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from ais_notify.sources.base import AISSource

logger = logging.getLogger(__name__)

_MAX_DATAGRAM = 4096


class _UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: asyncio.Queue[bytes]) -> None:
        self._queue = queue

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        # A single datagram may contain multiple NMEA sentences separated by newlines
        for line in data.splitlines():
            line = line.strip()
            if line:
                self._queue.put_nowait(line)

    def error_received(self, exc: Exception) -> None:
        logger.warning("UDP error: %s", exc)


class UDPSource(AISSource):
    """
    Listens on a local UDP port for NMEA sentences.

    rtl-ais default: rtl_ais -n -h 127.0.0.1 -P 10110
    AIS-catcher:     AIS-catcher -u 127.0.0.1 10110
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 10110) -> None:
        self._host = host
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    @property
    def name(self) -> str:
        return f"udp:{self._host}:{self._port}"

    async def _ensure_listening(self) -> None:
        if self._transport is None:
            loop = asyncio.get_running_loop()
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: _UDPProtocol(self._queue),
                local_addr=(self._host, self._port),
            )
            logger.info("UDP source listening on %s:%d", self._host, self._port)

    async def iter_sentences(self) -> AsyncIterator[bytes]:
        await self._ensure_listening()
        while True:
            yield await self._queue.get()

    async def close(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None
