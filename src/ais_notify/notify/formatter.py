"""
Message formatter for vessel sighting notifications.

Produces Telegram HTML-formatted strings.
All user-supplied data (vessel name, callsign, destination, etc.) is passed
through html.escape() before interpolation so that characters like <, >, &
don't break Telegram's HTML parser or cause silent delivery failures.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from ais_notify.enrich.shiptype import ship_type_emoji
from ais_notify.models import Vessel, VesselSignal

_NAV_STATUS = {
    0: "Underway (engine)",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Underway (sailing)",
    15: "Not defined",
}


def _e(value: str | None) -> str:
    """HTML-escape a string, returning empty string for None."""
    return html.escape(value) if value else ""


def _human_duration(dt: datetime) -> str:
    """Return a human-friendly 'X ago' string from a UTC datetime."""
    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m ago"
    days = seconds // 86400
    return f"{days}d ago"


def format_sighting(
    vessel: Vessel,
    signal: VesselSignal,
    last_seen: datetime | None,
    is_first_ever: bool,
) -> str:
    """Build a Telegram HTML notification for a new sighting."""
    name = _e(vessel.name) if vessel.name else f"MMSI {vessel.mmsi}"
    emoji = ship_type_emoji(vessel.ship_type)
    flag = vessel.flag_emoji or "🌐"

    lines: list[str] = []

    header = f"{emoji} <b>{name}</b> {flag}"
    if is_first_ever:
        header += "  <i>(first time seen!)</i>"
    lines.append(header)
    lines.append("")

    lines.append(f"📡 <b>MMSI:</b> {vessel.mmsi}")
    if vessel.imo:
        lines.append(f"🆔 <b>IMO:</b> {vessel.imo}")
    if vessel.callsign:
        lines.append(f"📻 <b>Callsign:</b> {_e(vessel.callsign)}")
    if vessel.ship_type_label:
        lines.append(f"🚢 <b>Type:</b> {_e(vessel.ship_type_label)}")
    if vessel.flag_country:
        lines.append(f"🏳️ <b>Flag:</b> {_e(vessel.flag_country)}")

    dims: list[str] = []
    if vessel.length_m:
        dims.append(f"{vessel.length_m:.0f}m long")
    if vessel.width_m:
        dims.append(f"{vessel.width_m:.0f}m wide")
    if vessel.draught:
        dims.append(f"{vessel.draught:.1f}m draught")
    if dims:
        lines.append(f"📐 <b>Size:</b> {', '.join(dims)}")

    if vessel.destination:
        dest_str = _e(vessel.destination)
        if vessel.eta:
            dest_str += f" (ETA: {_e(vessel.eta)})"
        lines.append(f"🗺️ <b>Destination:</b> {dest_str}")

    lines.append("")
    if signal.lat is not None and signal.lon is not None:
        lines.append(f"📍 <b>Position:</b> {signal.lat:.5f}, {signal.lon:.5f}")
        maps_url = f"https://www.google.com/maps?q={signal.lat},{signal.lon}"
        lines.append(f"🗾 <a href='{maps_url}'>Open on map</a>")
    if signal.sog is not None:
        lines.append(f"⚡ <b>Speed:</b> {signal.sog:.1f} kn")
    if signal.cog is not None:
        lines.append(f"🧭 <b>Course:</b> {signal.cog:.0f}°")
    if signal.nav_status is not None:
        status_label = _NAV_STATUS.get(signal.nav_status, f"Status {signal.nav_status}")
        lines.append(f"🔵 <b>Status:</b> {status_label}")

    lines.append("")
    if last_seen:
        lines.append(f"🕐 <b>Last seen:</b> {_human_duration(last_seen)}")
    else:
        lines.append("🆕 <b>Last seen:</b> Never before")

    return "\n".join(lines)


def format_daily_stats(stats: dict) -> str:
    """Build a Telegram HTML message for daily statistics."""
    date_label = _e(stats.get("date", "today"))
    lines = [
        f"📊 <b>Daily report — {date_label}</b>",
        "",
        f"📡 Signals processed: <b>{stats.get('total_sightings', 0)}</b>",
        f"🚢 Unique vessels: <b>{stats.get('unique_vessels', 0)}</b>",
        f"🆕 New vessels (first time): <b>{stats.get('new_vessels', 0)}</b>",
    ]
    if stats.get("busiest_hour") is not None:
        lines.append(
            f"⏰ Busiest hour: <b>{stats['busiest_hour']:02d}:00</b>"
            f" ({stats.get('busiest_hour_count', 0)} signals)"
        )

    type_breakdown = stats.get("type_breakdown", {})
    if type_breakdown:
        lines.append("")
        lines.append("📦 <b>By ship type:</b>")
        for label, count in sorted(type_breakdown.items(), key=lambda x: -x[1])[:8]:
            lines.append(f"  • {_e(label)}: {count}")

    top_vessels = stats.get("top_vessels", [])
    if top_vessels:
        lines.append("")
        lines.append("🏆 <b>Most seen vessels:</b>")
        for i, (name, count) in enumerate(top_vessels[:5], 1):
            lines.append(f"  {i}. {_e(name)}: {count} sightings")

    return "\n".join(lines)


def format_weekly_stats(stats: dict) -> str:
    """Build a Telegram HTML message for weekly statistics."""
    week_label = _e(stats.get("week", "this week"))
    lines = [
        f"📅 <b>Weekly report — {week_label}</b>",
        "",
        f"📡 Total signals: <b>{stats.get('total_sightings', 0)}</b>",
        f"🚢 Unique vessels: <b>{stats.get('unique_vessels', 0)}</b>",
        f"🆕 New vessels: <b>{stats.get('new_vessels', 0)}</b>",
        f"📆 Active days: <b>{stats.get('active_days', 0)}/7</b>",
    ]

    daily_trend = stats.get("daily_trend", [])
    if daily_trend:
        lines.append("")
        lines.append("📈 <b>Daily trend:</b>")
        max_count = max((c for _, c in daily_trend), default=1)
        for day_label, count in daily_trend:
            bar_len = round(count / max_count * 10)
            bar = "█" * bar_len
            lines.append(f"  {_e(day_label)}: {bar} {count}")

    type_breakdown = stats.get("type_breakdown", {})
    if type_breakdown:
        lines.append("")
        lines.append("📦 <b>By ship type:</b>")
        for label, count in sorted(type_breakdown.items(), key=lambda x: -x[1])[:8]:
            lines.append(f"  • {_e(label)}: {count}")

    return "\n".join(lines)
