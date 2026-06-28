"""
Stats aggregation — builds report dicts from pre-aggregated DB results.

The heavy GROUP BY work is done on the Postgres side (see schema.sql),
so this module receives compact summary data rather than raw sighting rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytz


def build_all_stats(summary: dict, first_date: datetime | None) -> dict:
    """Build an all-time stats dict from a stats_summary RPC result."""
    type_breakdown = {
        entry.get("ship_type_label") or "Unknown": int(entry["count"])
        for entry in (summary.get("type_breakdown") or [])
    }
    top_vessels = [
        (entry.get("name") or f"MMSI {entry['mmsi']}", int(entry["count"]))
        for entry in (summary.get("top_vessels") or [])
    ]
    return {
        "total_sightings": int(summary.get("total_sightings") or 0),
        "unique_vessels": int(summary.get("unique_vessels") or 0),
        "first_date": first_date,
        "type_breakdown": type_breakdown,
        "top_vessels": top_vessels,
    }


def _localise(iso_date: str, tz: Any) -> datetime:
    """Parse an ISO date string and attach a timezone for display purposes."""
    from datetime import date
    d = date.fromisoformat(iso_date)
    return tz.localize(datetime(d.year, d.month, d.day))


def build_daily_stats(
    summary: dict,
    new_mmsis: list[int],
    date_label: str,
    tz: Any = pytz.utc,
) -> dict:
    """
    Build a daily stats dict from a stats_summary RPC result.

    summary keys (from DB): total_sightings, unique_vessels,
      hourly_counts [{hour, count}], type_breakdown [{ship_type_label, count}],
      top_vessels [{name, mmsi, count}].
    """
    hourly = summary.get("hourly_counts") or []

    # Convert UTC hours to local hours
    utc_offset_hours = int(tz.utcoffset(datetime.now()).total_seconds() // 3600)
    hour_map: dict[int, int] = {}
    for entry in hourly:
        local_hour = (int(entry["hour"]) + utc_offset_hours) % 24
        hour_map[local_hour] = hour_map.get(local_hour, 0) + int(entry["count"])

    busiest_hour_entry = max(hour_map.items(), key=lambda x: x[1]) if hour_map else None

    type_breakdown = {
        entry.get("ship_type_label") or "Unknown": int(entry["count"])
        for entry in (summary.get("type_breakdown") or [])
    }

    top_vessels = [
        (entry.get("name") or f"MMSI {entry['mmsi']}", int(entry["count"]))
        for entry in (summary.get("top_vessels") or [])
    ]

    return {
        "date": date_label,
        "total_sightings": int(summary.get("total_sightings") or 0),
        "unique_vessels": int(summary.get("unique_vessels") or 0),
        "new_vessels": len(new_mmsis),
        "busiest_hour": busiest_hour_entry[0] if busiest_hour_entry else None,
        "busiest_hour_count": busiest_hour_entry[1] if busiest_hour_entry else 0,
        "type_breakdown": type_breakdown,
        "top_vessels": top_vessels,
    }


def build_weekly_stats(
    summary: dict,
    daily_counts: list[dict],
    new_mmsis: list[int],
    week_label: str,
    tz: Any = pytz.utc,
) -> dict:
    """
    Build a weekly stats dict.

    summary: from stats_summary RPC (same keys as daily).
    daily_counts: from daily_sighting_counts RPC — [{day_iso, count}, ...].
    """
    # Build chronologically sorted trend with local day labels
    daily_trend = []
    active_days = 0
    for entry in sorted(daily_counts, key=lambda x: x["day_iso"]):
        count = int(entry["count"])
        if count > 0:
            active_days += 1
        dt = _localise(entry["day_iso"], tz)
        daily_trend.append((dt.strftime("%a %d"), count))

    type_breakdown = {
        entry.get("ship_type_label") or "Unknown": int(entry["count"])
        for entry in (summary.get("type_breakdown") or [])
    }

    return {
        "week": week_label,
        "total_sightings": int(summary.get("total_sightings") or 0),
        "unique_vessels": int(summary.get("unique_vessels") or 0),
        "new_vessels": len(new_mmsis),
        "active_days": active_days,
        "daily_trend": daily_trend,
        "type_breakdown": type_breakdown,
    }
