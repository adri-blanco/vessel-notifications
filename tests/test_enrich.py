"""Tests for enrichment providers."""

import asyncio
import pytest

from ais_notify.enrich.ais_static import AISStaticEnricher
from ais_notify.enrich.shiptype import ship_type_label, ship_type_emoji
from ais_notify.enrich.mmsi import mid_lookup
from ais_notify.models import Vessel, VesselSignal
from datetime import datetime, timezone


def _signal(**kwargs):
    defaults = dict(mmsi=123456789, ts=datetime.now(timezone.utc), source="test")
    defaults.update(kwargs)
    return VesselSignal(**defaults)


def test_ship_type_label_cargo():
    assert ship_type_label(70) == "Cargo"


def test_ship_type_label_tanker():
    assert ship_type_label(80) == "Tanker"


def test_ship_type_label_unknown():
    assert ship_type_label(None) == "Unknown"


def test_ship_type_emoji_passenger():
    assert ship_type_emoji(60) == "🛳️"


def test_mmsi_mid_lookup_spain():
    country, emoji = mid_lookup(224123456)
    assert country == "Spain"
    assert emoji == "🇪🇸"


def test_mmsi_mid_lookup_germany():
    country, emoji = mid_lookup(211234560)
    assert country == "Germany"
    assert emoji == "🇩🇪"


def test_mmsi_mid_lookup_unknown():
    country, emoji = mid_lookup(999999999)
    assert country == "Unknown"


def test_ais_static_enricher_applies_signal_data():
    enricher = AISStaticEnricher()
    vessel = Vessel(mmsi=224123456)
    signal = _signal(
        mmsi=224123456,
        name="VESSEL TEST",
        callsign="EA1ABC",
        ship_type=70,
        length=120.0,
        width=18.0,
    )
    result = asyncio.run(enricher.enrich(vessel, signal))
    assert result.name == "VESSEL TEST"
    assert result.ship_type_label == "Cargo"
    assert result.flag_country == "Spain"
    assert result.length_m == 120.0


def test_ais_static_enricher_does_not_overwrite_existing():
    enricher = AISStaticEnricher()
    vessel = Vessel(mmsi=224123456, name="EXISTING NAME")
    signal = _signal(mmsi=224123456, name="NEW NAME")
    result = asyncio.run(enricher.enrich(vessel, signal))
    assert result.name == "EXISTING NAME"
