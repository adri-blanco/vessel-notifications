"""
Signal handler — the core pipeline step between decoder and storage/notification.

For each VesselSignal that passes dedup:
  1. Dedup check (returns last_seen timestamp so no second DB call is needed).
  2. Load or initialise a Vessel record.
  3. Apply enrichment chain.
  4. Send Telegram notification (fast path — before the DB writes).
  5. Persist sighting + upsert vessel asynchronously.
"""

from __future__ import annotations

import asyncio
import logging

from ais_notify.db.repository import Repository
from ais_notify.dedup import DedupCache
from ais_notify.enrich.ais_static import AISStaticEnricher
from ais_notify.enrich.photo import PhotoEnricher, run_enrichment_chain
from ais_notify.models import Sighting, Vessel, VesselSignal
from ais_notify.notify.base import Notifier
from ais_notify.notify.formatter import format_sighting

logger = logging.getLogger(__name__)

_ENRICH_PROVIDERS = [AISStaticEnricher(), PhotoEnricher()]


class SignalHandler:
    def __init__(
        self,
        repo: Repository,
        notifier: Notifier,
        dedup: DedupCache,
    ) -> None:
        self._repo = repo
        self._notifier = notifier
        self._dedup = dedup

    async def handle(self, signal: VesselSignal) -> None:
        # ── 1. Dedup check ───────────────────────────────────────────────
        # check() returns (is_duplicate, last_seen_ts) in one DB call.
        # last_seen_ts is reused in the notification — no second query needed.
        is_dup, last_seen = await self._dedup.check(signal.mmsi, self._repo)
        if is_dup:
            return

        # ── 2. Load existing vessel or create a stub ─────────────────────
        vessel = await self._repo.get_vessel(signal.mmsi)
        is_first_ever = vessel is None
        if vessel is None:
            vessel = Vessel(mmsi=signal.mmsi, first_seen=signal.ts)

        # ── 3. Enrich ────────────────────────────────────────────────────
        vessel = await run_enrichment_chain(vessel, signal, _ENRICH_PROVIDERS)

        # ── 4. Send Telegram (fast path, before DB writes) ───────────────
        try:
            message = format_sighting(vessel, signal, last_seen, is_first_ever)
            asyncio.create_task(
                self._notifier.send_message(message, photo_url=vessel.photo_url)
            )
        except Exception as exc:
            logger.error("Failed to format/send Telegram for MMSI %d: %s", signal.mmsi, exc)

        # ── 5. Mark dedup cache immediately ──────────────────────────────
        self._dedup.mark_seen(signal.mmsi, signal.ts)

        # ── 6. Persist (fire-and-forget) ─────────────────────────────────
        sighting = Sighting(
            mmsi=signal.mmsi,
            ts=signal.ts,
            lat=signal.lat,
            lon=signal.lon,
            sog=signal.sog,
            cog=signal.cog,
            heading=signal.heading,
            nav_status=signal.nav_status,
            source=signal.source,
            raw=signal.raw,
        )
        asyncio.create_task(self._persist(vessel, sighting, is_first_ever))

    async def _persist(self, vessel: Vessel, sighting: Sighting, is_first_ever: bool) -> None:
        if is_first_ever:
            # Vessel row must exist before sighting (FK constraint).
            # If upsert fails, skip the sighting insert to avoid a FK violation
            # that would also fail silently and lose the sighting.
            ok = await self._repo.upsert_vessel(vessel)
            if not ok:
                logger.error(
                    "Skipping sighting insert for MMSI %d: vessel upsert failed",
                    vessel.mmsi,
                )
                return
            await self._repo.insert_sighting(sighting)
        else:
            # Existing vessel: insert the sighting first, then update enriched fields.
            await self._repo.insert_sighting(sighting)
            await self._repo.upsert_vessel(vessel)
