"""
Deduplication gate — prevents processing the same vessel more than once
per dedup window (default 5 minutes).

Two-layer check:
1. In-memory TTL dict (microsecond latency, resets on restart).
2. DB fallback via repository.get_last_sighting (survives restarts).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ais_notify.db.repository import Repository

logger = logging.getLogger(__name__)


class DedupCache:
    """
    Per-MMSI TTL cache backed by a DB fallback on cold start.

    thread-safe for asyncio (single event loop, no actual threads here).
    """

    def __init__(self, window_seconds: int = 300) -> None:
        self._window = window_seconds
        # mmsi -> last accepted timestamp (UTC)
        self._cache: dict[int, datetime] = {}

    def _is_within_window(self, last_seen: datetime | None) -> bool:
        if last_seen is None:
            return False
        now = datetime.now(timezone.utc)
        # Ensure last_seen is tz-aware
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        return (now - last_seen).total_seconds() < self._window

    def check_memory(self, mmsi: int) -> bool:
        """
        Return True if the MMSI is within the dedup window (in memory).
        Returns False if not found in memory (DB check required).
        """
        last = self._cache.get(mmsi)
        return self._is_within_window(last)

    async def check(
        self, mmsi: int, repo: "Repository"
    ) -> tuple[bool, datetime | None]:
        """
        Full two-layer check.

        Returns (is_duplicate, last_seen_ts) so the caller can reuse the
        timestamp without a second DB round trip.

        is_duplicate=True  → skip this signal entirely.
        is_duplicate=False → process; last_seen_ts is the previous sighting
                             time (or None if never seen) for the notification.
        """
        # Fast path: memory hit — we already know it's within the window
        last_mem = self._cache.get(mmsi)
        if self._is_within_window(last_mem):
            logger.debug("Dedup memory hit for MMSI %d", mmsi)
            return True, last_mem

        # Cold-start / restart fallback: check DB (one round trip, reused below)
        last_db = await repo.get_last_sighting(mmsi)
        if self._is_within_window(last_db):
            self._cache[mmsi] = last_db  # type: ignore[assignment]
            logger.debug("Dedup DB hit for MMSI %d (last=%s)", mmsi, last_db)
            return True, last_db

        # Not a duplicate — return the last-seen time for the notification
        return False, last_db

    def mark_seen(self, mmsi: int, ts: datetime) -> None:
        """Record that we just processed this MMSI."""
        self._cache[mmsi] = ts

    def evict_expired(self) -> int:
        """Remove entries older than the window. Call periodically to keep memory bounded."""
        now = datetime.now(timezone.utc)
        expired = [
            mmsi
            for mmsi, ts in self._cache.items()
            if (now - ts).total_seconds() >= self._window
        ]
        for mmsi in expired:
            del self._cache[mmsi]
        if expired:
            logger.debug("Dedup evicted %d expired entries", len(expired))
        return len(expired)
