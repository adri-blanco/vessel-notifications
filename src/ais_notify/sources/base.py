"""Abstract base class for all AIS input sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class AISSource(ABC):
    """
    A swappable input adapter that yields raw NMEA sentences.

    Implementations: UDPSource, TCPSource, SerialSource, FileSource.
    Each must implement `iter_sentences()` as an async generator that
    yields bytes lines (without trailing newline/CRLF) representing
    individual NMEA/AIVDM sentences.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier used for logging and stored in sightings.source."""

    @abstractmethod
    def iter_sentences(self) -> AsyncIterator[bytes]:
        """Yield raw NMEA sentence bytes, one per line, indefinitely (or until EOF)."""

    async def close(self) -> None:
        """Override to release resources (sockets, serial ports, file handles)."""
