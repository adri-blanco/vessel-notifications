"""Tests for stats query builders."""

import pytz
from ais_notify.stats.queries import build_daily_stats, build_weekly_stats

_UTC = pytz.utc
_MADRID = pytz.timezone("Europe/Madrid")


def _summary(total=42, unique=15, hourly=None, type_bd=None, top=None):
    return {
        "total_sightings": total,
        "unique_vessels": unique,
        "hourly_counts": hourly or [{"hour": 14, "count": 8}, {"hour": 10, "count": 3}],
        "type_breakdown": type_bd or [
            {"ship_type_label": "Cargo", "count": 20},
            {"ship_type_label": "Tanker", "count": 10},
        ],
        "top_vessels": top or [
            {"name": "VESSEL A", "mmsi": 123, "count": 12},
            {"name": "VESSEL B", "mmsi": 456, "count": 8},
        ],
    }


def test_build_daily_stats_basic():
    stats = build_daily_stats(_summary(), new_mmsis=[1, 2, 3], date_label="Monday, 28 Jun 2026")
    assert stats["total_sightings"] == 42
    assert stats["unique_vessels"] == 15
    assert stats["new_vessels"] == 3
    assert stats["date"] == "Monday, 28 Jun 2026"


def test_build_daily_stats_type_breakdown():
    stats = build_daily_stats(_summary(), new_mmsis=[], date_label="test")
    assert stats["type_breakdown"]["Cargo"] == 20
    assert stats["type_breakdown"]["Tanker"] == 10


def test_build_daily_stats_top_vessels():
    stats = build_daily_stats(_summary(), new_mmsis=[], date_label="test")
    assert stats["top_vessels"][0] == ("VESSEL A", 12)


def test_build_daily_stats_busiest_hour_utc():
    stats = build_daily_stats(_summary(), new_mmsis=[], date_label="test", tz=_UTC)
    assert stats["busiest_hour"] == 14


def test_build_daily_stats_busiest_hour_local():
    # UTC+2: hour 14 UTC -> hour 16 local
    stats = build_daily_stats(_summary(), new_mmsis=[], date_label="test", tz=_MADRID)
    assert stats["busiest_hour"] == 16


def _daily_counts():
    return [
        {"day_iso": "2026-06-23", "count": 40},
        {"day_iso": "2026-06-24", "count": 35},
        {"day_iso": "2026-06-25", "count": 50},
        {"day_iso": "2026-06-26", "count": 30},
        {"day_iso": "2026-06-27", "count": 45},
        {"day_iso": "2026-06-28", "count": 20},
    ]


def test_build_weekly_stats_chronological_order():
    stats = build_weekly_stats(
        _summary(total=220, unique=60),
        _daily_counts(),
        new_mmsis=[1, 2],
        week_label="23 Jun – 28 Jun 2026",
        tz=_UTC,
    )
    dates = [label for label, _ in stats["daily_trend"]]
    # Must be in chronological order, not alphabetical
    # 2026-06-23 is a Tuesday; verify chronological order, not alphabetical
    assert dates == ["Tue 23", "Wed 24", "Thu 25", "Fri 26", "Sat 27", "Sun 28"]


def test_build_weekly_stats_active_days():
    stats = build_weekly_stats(
        _summary(),
        _daily_counts(),
        new_mmsis=[],
        week_label="test",
        tz=_UTC,
    )
    assert stats["active_days"] == 6
