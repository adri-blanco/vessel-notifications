"""Tests for Telegram message formatter."""

from datetime import datetime, timedelta, timezone

from ais_notify.models import Vessel, VesselSignal
from ais_notify.notify.formatter import format_sighting, format_daily_stats, format_weekly_stats


def _vessel():
    return Vessel(
        mmsi=224123456,
        name="TEST VESSEL",
        imo=9123456,
        callsign="EA1ABC",
        ship_type=70,
        ship_type_label="Cargo",
        length_m=150.0,
        width_m=22.0,
        flag_country="Spain",
        flag_emoji="🇪🇸",
        destination="BARCELONA",
    )


def _signal():
    return VesselSignal(
        mmsi=224123456,
        ts=datetime.now(timezone.utc),
        source="test",
        lat=41.38,
        lon=2.18,
        sog=5.2,
        cog=90.0,
        nav_status=0,
    )


def test_format_sighting_first_ever():
    msg = format_sighting(_vessel(), _signal(), last_seen=None, is_first_ever=True)
    assert "TEST VESSEL" in msg
    assert "first time seen" in msg
    assert "Spain" in msg
    assert "41.38" in msg
    assert "vesselFinder.com/?mmsi=224123456" in msg


def test_format_sighting_vesselfinder_link_always_present():
    signal_no_pos = VesselSignal(mmsi=224123456, ts=datetime.now(timezone.utc), source="test")
    msg = format_sighting(_vessel(), signal_no_pos, last_seen=None, is_first_ever=False)
    assert "vesselFinder.com/?mmsi=224123456" in msg


def test_format_sighting_with_last_seen():
    last = datetime.now(timezone.utc) - timedelta(hours=2)
    msg = format_sighting(_vessel(), _signal(), last_seen=last, is_first_ever=False)
    assert "Last seen" in msg
    assert "ago" in msg


def test_format_daily_stats():
    stats = {
        "date": "Monday, 28 Jun 2026",
        "total_sightings": 42,
        "unique_vessels": 15,
        "new_vessels": 3,
        "busiest_hour": 14,
        "busiest_hour_count": 8,
        "type_breakdown": {"Cargo": 20, "Tanker": 10, "Passenger": 5, "Unknown": 7},
        "top_vessels": [("VESSEL A", 12), ("VESSEL B", 8)],
    }
    msg = format_daily_stats(stats)
    assert "42" in msg
    assert "15" in msg
    assert "Cargo" in msg
    assert "VESSEL A" in msg


def test_format_weekly_stats():
    stats = {
        "week": "22 Jun – 28 Jun 2026",
        "total_sightings": 300,
        "unique_vessels": 80,
        "new_vessels": 12,
        "active_days": 7,
        "daily_trend": [("Mon 22", 40), ("Tue 23", 35), ("Wed 24", 50)],
        "type_breakdown": {"Cargo": 150, "Tanker": 80},
    }
    msg = format_weekly_stats(stats)
    assert "300" in msg
    assert "Mon 22" in msg
    assert "Cargo" in msg
