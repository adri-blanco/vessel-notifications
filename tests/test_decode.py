"""Smoke tests for the decoder using the sample NMEA file."""

import asyncio
import pytest

from ais_notify.sources.file_source import FileSource
from ais_notify.decode import AISDecoder


SAMPLE = "tests/sample.nmea"


def _collect(loop_flag: bool = False):
    async def _run():
        source = FileSource(SAMPLE, loop=loop_flag)
        decoder = AISDecoder(source)
        signals = []
        async for sig in decoder.iter_signals():
            signals.append(sig)
        return signals

    return asyncio.run(_run())


def test_decode_produces_signals():
    signals = _collect()
    assert len(signals) >= 1, "Expected at least one decoded signal from sample.nmea"


def test_signals_have_mmsi():
    signals = _collect()
    for sig in signals:
        assert isinstance(sig.mmsi, int)
        assert sig.mmsi > 0


def test_position_signals_have_coords():
    signals = _collect()
    position_signals = [s for s in signals if s.lat is not None]
    assert len(position_signals) >= 1, "Expected at least one signal with coordinates"
    for sig in position_signals:
        assert -90 <= sig.lat <= 90
        assert -180 <= sig.lon <= 180
