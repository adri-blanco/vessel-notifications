"""Tests for dedup cache logic."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from ais_notify.dedup import DedupCache


class _FakeRepo:
    def __init__(self, last: datetime | None):
        self._last = last

    async def get_last_sighting(self, mmsi: int):
        return self._last


def test_not_duplicate_when_never_seen():
    cache = DedupCache(window_seconds=300)
    repo = _FakeRepo(last=None)
    is_dup, last_seen = asyncio.run(cache.check(123456789, repo))
    assert is_dup is False
    assert last_seen is None


def test_duplicate_when_seen_recently():
    cache = DedupCache(window_seconds=300)
    recent = datetime.now(timezone.utc) - timedelta(seconds=30)
    repo = _FakeRepo(last=recent)
    is_dup, last_seen = asyncio.run(cache.check(123456789, repo))
    assert is_dup is True
    assert last_seen == recent


def test_not_duplicate_after_window_expired():
    cache = DedupCache(window_seconds=300)
    old = datetime.now(timezone.utc) - timedelta(seconds=400)
    repo = _FakeRepo(last=old)
    is_dup, last_seen = asyncio.run(cache.check(123456789, repo))
    assert is_dup is False
    assert last_seen == old


def test_last_seen_returned_for_notification():
    """The last_seen timestamp from check() should be usable without a second DB call."""
    cache = DedupCache(window_seconds=300)
    old = datetime.now(timezone.utc) - timedelta(seconds=400)
    repo = _FakeRepo(last=old)
    is_dup, last_seen = asyncio.run(cache.check(111222333, repo))
    assert is_dup is False
    assert last_seen is old  # same object — no extra query


def test_memory_cache_hit():
    cache = DedupCache(window_seconds=300)
    now = datetime.now(timezone.utc)
    cache.mark_seen(111222333, now)
    assert cache.check_memory(111222333) is True


def test_evict_expired():
    cache = DedupCache(window_seconds=1)
    old = datetime.now(timezone.utc) - timedelta(seconds=10)
    cache._cache[999] = old
    evicted = cache.evict_expired()
    assert evicted == 1
    assert 999 not in cache._cache
