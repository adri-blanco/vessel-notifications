"""
Decodes raw NMEA/AIVDM sentences into VesselSignal objects.

Supports:
  - Message types 1, 2, 3: Class A position
  - Message type 18:       Class B position
  - Message type 5:        Class A static & voyage
  - Message type 21:       Aids-to-navigation (AtoN)
  - Message type 24:       Class B static (part A/B)

Multi-part messages (e.g. type 5 split across two !AIVDM sentences) are
assembled here before decoding.

pyais 3.x API: decode(*raw_bytes_parts) — pass raw sentence bytes directly.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import AsyncIterator

from pyais import decode as pyais_decode

from ais_notify.models import VesselSignal
from ais_notify.sources.base import AISSource

logger = logging.getLogger(__name__)

# AIS message types that carry position data
_POSITION_TYPES = {1, 2, 3, 18, 21}
# AIS message types that carry static/voyage data
_STATIC_TYPES = {5, 24}
# All types we care to process
_HANDLED_TYPES = _POSITION_TYPES | _STATIC_TYPES

# Incomplete multi-part messages older than this are dropped
_FRAGMENT_TTL_SECONDS = 30
# Check and evict stale fragments every N messages
_FRAGMENT_EVICT_INTERVAL = 500


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    # AIS uses 91.0/181.0 as "not available" sentinels for lat/lon
    if f in (91.0, -91.0, 181.0, -181.0):
        return None
    return f


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip().strip("@")
    return s if s else None


class AISDecoder:
    """
    Wraps an AISSource and yields decoded VesselSignal objects.

    Multi-part messages are buffered until all fragments arrive, then decoded
    together using pyais.decode(*parts).
    """

    def __init__(self, source: AISSource) -> None:
        self._source = source
        # seq_key -> (arrival_time, list[raw_sentence_bytes])
        self._fragments: dict[str, tuple[float, list[bytes]]] = {}
        self._msg_count = 0

    async def iter_signals(self) -> AsyncIterator[VesselSignal]:
        async for raw_line in self._source.iter_sentences():
            try:
                signal = await self._process_line(raw_line)
                if signal is not None:
                    yield signal
            except Exception as exc:
                logger.debug("Unhandled error processing line %r: %s", raw_line, exc)

            self._msg_count += 1
            if self._msg_count % _FRAGMENT_EVICT_INTERVAL == 0:
                self._evict_stale_fragments()

    async def _process_line(self, raw_line: bytes) -> VesselSignal | None:
        sentence = raw_line.decode("ascii", errors="replace").strip()
        if not sentence.startswith("!AIVDM") and not sentence.startswith("!AIVDO"):
            return None

        parts = sentence.split(",")
        if len(parts) < 7:
            return None

        try:
            total_parts = int(parts[1])
            part_num = int(parts[2])
        except (ValueError, IndexError):
            return None

        seq_id = parts[3]  # sequential message identifier (empty for single-part)

        if total_parts > 1:
            # Buffer fragments until we have all of them
            key = f"{seq_id or 'x'}:{total_parts}"
            if key not in self._fragments:
                self._fragments[key] = (time.monotonic(), [])
            arrival, parts = self._fragments[key]
            parts.append(raw_line)

            if len(parts) < total_parts:
                return None

            assembled = self._fragments.pop(key)[1]
            return self._decode_parts(assembled)
        else:
            return self._decode_parts([raw_line])

    def _evict_stale_fragments(self) -> None:
        now = time.monotonic()
        stale = [
            key
            for key, (arrival, _) in self._fragments.items()
            if now - arrival > _FRAGMENT_TTL_SECONDS
        ]
        for key in stale:
            logger.debug("Evicting incomplete fragment buffer: %s", key)
            del self._fragments[key]
        if stale:
            logger.debug("Fragment eviction removed %d incomplete messages", len(stale))

    def _decode_parts(self, raw_parts: list[bytes]) -> VesselSignal | None:
        try:
            msg = pyais_decode(*raw_parts)
        except Exception as exc:
            logger.debug("pyais decode error: %s", exc)
            return None

        msg_type = msg.msg_type
        if msg_type not in _HANDLED_TYPES:
            return None

        mmsi = _safe_int(getattr(msg, "mmsi", None))
        if not mmsi:
            return None

        ts = datetime.now(timezone.utc)
        raw_str = " | ".join(p.decode("ascii", errors="replace").strip() for p in raw_parts)

        signal = VesselSignal(
            mmsi=mmsi,
            ts=ts,
            source=self._source.name,
            msg_type=msg_type,
            raw=raw_str,
        )

        if msg_type in _POSITION_TYPES:
            lat = _safe_float(getattr(msg, "lat", None))
            lon = _safe_float(getattr(msg, "lon", None))
            # Discard positions exactly at 0,0 (null island sentinel)
            if lat is not None and lon is not None and not (lat == 0.0 and lon == 0.0):
                signal.lat = lat
                signal.lon = lon
            signal.sog = _safe_float(getattr(msg, "speed", None))
            signal.cog = _safe_float(getattr(msg, "course", None))
            signal.heading = _safe_int(getattr(msg, "heading", None))
            signal.nav_status = _safe_int(getattr(msg, "status", None))

        if msg_type in _STATIC_TYPES:
            signal.name = _clean_str(getattr(msg, "shipname", None))
            signal.callsign = _clean_str(getattr(msg, "callsign", None))
            imo = _safe_int(getattr(msg, "imo", None))
            signal.imo = imo if imo and imo > 0 else None
            signal.ship_type = _safe_int(getattr(msg, "ship_type", None))

            to_bow = _safe_float(getattr(msg, "to_bow", None))
            to_stern = _safe_float(getattr(msg, "to_stern", None))
            to_port = _safe_float(getattr(msg, "to_port", None))
            to_starboard = _safe_float(getattr(msg, "to_starboard", None))
            if to_bow is not None and to_stern is not None:
                signal.length = to_bow + to_stern
            if to_port is not None and to_starboard is not None:
                signal.width = to_port + to_starboard

            signal.draught = _safe_float(getattr(msg, "draught", None))
            signal.destination = _clean_str(getattr(msg, "destination", None))
            eta_raw = getattr(msg, "eta", None)
            signal.eta = str(eta_raw) if eta_raw else None

        return signal
