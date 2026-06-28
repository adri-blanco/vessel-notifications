"""Core domain dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class VesselSignal:
    """Decoded AIS signal, normalised from any message type."""

    mmsi: int
    ts: datetime
    source: str  # identifies which AISSource produced this

    # Position (msgs 1/2/3/18/21)
    lat: float | None = None
    lon: float | None = None
    sog: float | None = None   # speed over ground (knots)
    cog: float | None = None   # course over ground (degrees)
    heading: int | None = None
    nav_status: int | None = None  # AIS navigational status code

    # Static / voyage data (msg 5/24)
    name: str | None = None
    callsign: str | None = None
    imo: int | None = None
    ship_type: int | None = None
    length: float | None = None   # metres
    width: float | None = None    # metres
    draught: float | None = None  # metres
    destination: str | None = None
    eta: str | None = None

    # Original message type for traceability
    msg_type: int | None = None
    # Raw NMEA sentence(s) for debugging
    raw: str | None = None


@dataclass
class Vessel:
    """Persistent vessel record (mirrors the DB `vessels` table)."""

    mmsi: int
    name: str | None = None
    imo: int | None = None
    callsign: str | None = None
    ship_type: int | None = None
    ship_type_label: str | None = None
    length_m: float | None = None
    width_m: float | None = None
    draught: float | None = None
    destination: str | None = None
    eta: str | None = None
    flag_country: str | None = None
    flag_emoji: str | None = None
    photo_url: str | None = None
    info: dict[str, Any] = field(default_factory=dict)
    first_seen: datetime | None = None
    last_enriched: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Sighting:
    """A single time/position observation of a vessel."""

    mmsi: int
    ts: datetime
    lat: float | None = None
    lon: float | None = None
    sog: float | None = None
    cog: float | None = None
    heading: int | None = None
    nav_status: int | None = None
    source: str = "unknown"
    raw: str | None = None
