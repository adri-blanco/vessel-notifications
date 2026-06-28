"""Serial source — reads NMEA from a hardware serial port (e.g. dAISy HAT)."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from ais_notify.sources.base import AISSource

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 5.0


class SerialSource(AISSource):
    """
    Reads NMEA sentences from a serial port using pyserial in a thread.

    Typical config: /dev/ttyAMA0 (dAISy HAT on Pi) at 38400 baud.
    """

    def __init__(self, port: str = "/dev/ttyAMA0", baud: int = 38400) -> None:
        self._port = port
        self._baud = baud

    @property
    def name(self) -> str:
        return f"serial:{self._port}"

    async def iter_sentences(self) -> AsyncIterator[bytes]:
        while True:
            try:
                import serial  # lazy import; pyserial is optional when using UDP/TCP

                loop = asyncio.get_running_loop()
                ser = await loop.run_in_executor(
                    None,
                    lambda: serial.Serial(self._port, self._baud, timeout=1),
                )
                logger.info("Serial source opened %s at %d baud", self._port, self._baud)
                try:
                    while True:
                        line: bytes = await loop.run_in_executor(None, ser.readline)
                        line = line.strip()
                        if line:
                            yield line
                finally:
                    ser.close()
                logger.warning("Serial port closed, reconnecting in %ss", _RECONNECT_DELAY)
            except Exception as exc:
                logger.warning("Serial source error (%s), retrying in %ss", exc, _RECONNECT_DELAY)
            await asyncio.sleep(_RECONNECT_DELAY)
