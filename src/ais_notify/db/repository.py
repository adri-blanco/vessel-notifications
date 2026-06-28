"""
Database repository — all SQL interactions go through here.

Uses the Supabase Python client (postgrest-py under the hood).
Every method that touches the network is wrapped in asyncio.to_thread
so the async event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from supabase import Client

from ais_notify.models import Vessel, Sighting

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, client: Client) -> None:
        self._db = client

    # ------------------------------------------------------------------
    # Vessels
    # ------------------------------------------------------------------

    def _upsert_vessel_sync(self, vessel: Vessel) -> None:
        row: dict[str, Any] = {"mmsi": vessel.mmsi}
        if vessel.name is not None:
            row["name"] = vessel.name
        if vessel.imo is not None:
            row["imo"] = vessel.imo
        if vessel.callsign is not None:
            row["callsign"] = vessel.callsign
        if vessel.ship_type is not None:
            row["ship_type"] = vessel.ship_type
        if vessel.ship_type_label is not None:
            row["ship_type_label"] = vessel.ship_type_label
        if vessel.length_m is not None:
            row["length_m"] = vessel.length_m
        if vessel.width_m is not None:
            row["width_m"] = vessel.width_m
        if vessel.draught is not None:
            row["draught"] = vessel.draught
        if vessel.destination is not None:
            row["destination"] = vessel.destination
        if vessel.eta is not None:
            row["eta"] = vessel.eta
        if vessel.flag_country is not None:
            row["flag_country"] = vessel.flag_country
        if vessel.flag_emoji is not None:
            row["flag_emoji"] = vessel.flag_emoji
        if vessel.photo_url is not None:
            row["photo_url"] = vessel.photo_url
        if vessel.info:
            row["info"] = vessel.info
        if vessel.last_enriched is not None:
            row["last_enriched"] = vessel.last_enriched.isoformat()

        (
            self._db.table("vessels")
            .upsert(row, on_conflict="mmsi", ignore_duplicates=False)
            .execute()
        )

    async def upsert_vessel(self, vessel: Vessel) -> bool:
        """Return True on success, False on failure."""
        try:
            await asyncio.to_thread(self._upsert_vessel_sync, vessel)
            return True
        except Exception as exc:
            logger.error("upsert_vessel failed for MMSI %d: %s", vessel.mmsi, exc)
            return False

    def _get_vessel_sync(self, mmsi: int) -> Vessel | None:
        res = (
            self._db.table("vessels")
            .select("*")
            .eq("mmsi", mmsi)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        row = res.data[0]
        return Vessel(
            mmsi=row["mmsi"],
            name=row.get("name"),
            imo=row.get("imo"),
            callsign=row.get("callsign"),
            ship_type=row.get("ship_type"),
            ship_type_label=row.get("ship_type_label"),
            length_m=row.get("length_m"),
            width_m=row.get("width_m"),
            draught=row.get("draught"),
            destination=row.get("destination"),
            eta=row.get("eta"),
            flag_country=row.get("flag_country"),
            flag_emoji=row.get("flag_emoji"),
            photo_url=row.get("photo_url"),
            info=row.get("info") or {},
            first_seen=row.get("first_seen"),
            last_enriched=row.get("last_enriched"),
            updated_at=row.get("updated_at"),
        )

    async def get_vessel(self, mmsi: int) -> Vessel | None:
        try:
            return await asyncio.to_thread(self._get_vessel_sync, mmsi)
        except Exception as exc:
            logger.error("get_vessel failed for MMSI %d: %s", mmsi, exc)
            return None

    # ------------------------------------------------------------------
    # Sightings
    # ------------------------------------------------------------------

    def _insert_sighting_sync(self, sighting: Sighting) -> None:
        row: dict[str, Any] = {
            "mmsi": sighting.mmsi,
            "ts": sighting.ts.isoformat(),
            "source": sighting.source,
        }
        if sighting.lat is not None:
            row["lat"] = float(sighting.lat)
        if sighting.lon is not None:
            row["lon"] = float(sighting.lon)
        if sighting.sog is not None:
            row["sog"] = float(sighting.sog)
        if sighting.cog is not None:
            row["cog"] = float(sighting.cog)
        if sighting.heading is not None:
            row["heading"] = int(sighting.heading)
        if sighting.nav_status is not None:
            row["nav_status"] = int(sighting.nav_status)
        if sighting.direction is not None:
            row["direction"] = sighting.direction
        if sighting.raw is not None:
            row["raw"] = sighting.raw

        self._db.table("sightings").insert(row).execute()

    async def insert_sighting(self, sighting: Sighting) -> None:
        try:
            await asyncio.to_thread(self._insert_sighting_sync, sighting)
        except Exception as exc:
            logger.error("insert_sighting failed for MMSI %d: %s", sighting.mmsi, exc)

    def _get_last_sighting_sync(self, mmsi: int) -> datetime | None:
        res = (
            self._db.table("sightings")
            .select("ts")
            .eq("mmsi", mmsi)
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        ts_str = res.data[0]["ts"]
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)

    async def get_last_sighting(self, mmsi: int) -> datetime | None:
        """Return the UTC timestamp of the most recent sighting for this MMSI."""
        try:
            return await asyncio.to_thread(self._get_last_sighting_sync, mmsi)
        except Exception as exc:
            logger.error("get_last_sighting failed for MMSI %d: %s", mmsi, exc)
            return None

    # ------------------------------------------------------------------
    # Stats helpers — aggregated on the DB side to avoid loading all rows
    # ------------------------------------------------------------------

    def _stats_summary_sync(self, since: datetime, until: datetime) -> dict:
        """
        Run all stats aggregations in a single RPC call via Supabase's
        PostgREST SQL function.  The function is defined in schema.sql.

        Returns a dict with keys:
          total_sightings, unique_vessels,
          hourly_counts (list of {hour, count}),
          type_breakdown (list of {ship_type_label, count}),
          top_vessels (list of {name, mmsi, count})
        """
        res = self._db.rpc(
            "stats_summary",
            {"p_since": since.isoformat(), "p_until": until.isoformat()},
        ).execute()
        return res.data[0] if res.data else {}

    async def stats_summary(self, since: datetime, until: datetime) -> dict:
        try:
            return await asyncio.to_thread(self._stats_summary_sync, since, until)
        except Exception as exc:
            logger.error("stats_summary failed: %s", exc)
            return {}

    def _daily_sighting_counts_sync(self, since: datetime, until: datetime) -> list[dict]:
        """
        Return per-day sighting counts for the range.
        Each row: {day_iso: '2026-06-23', count: N}
        """
        res = self._db.rpc(
            "daily_sighting_counts",
            {"p_since": since.isoformat(), "p_until": until.isoformat()},
        ).execute()
        return res.data or []

    async def daily_sighting_counts(self, since: datetime, until: datetime) -> list[dict]:
        try:
            return await asyncio.to_thread(self._daily_sighting_counts_sync, since, until)
        except Exception as exc:
            logger.error("daily_sighting_counts failed: %s", exc)
            return []

    def _get_first_sighting_date_sync(self) -> datetime | None:
        """Return the UTC timestamp of the earliest vessel first_seen ever recorded."""
        res = (
            self._db.table("vessels")
            .select("first_seen")
            .order("first_seen", desc=False)
            .limit(1)
            .execute()
        )
        if not res.data or not res.data[0].get("first_seen"):
            return None
        ts_str = res.data[0]["first_seen"]
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(timezone.utc)

    async def get_first_sighting_date(self) -> datetime | None:
        """Return the UTC datetime of the very first vessel ever recorded, or None."""
        try:
            return await asyncio.to_thread(self._get_first_sighting_date_sync)
        except Exception as exc:
            logger.error("get_first_sighting_date failed: %s", exc)
            return None

    def _first_seen_in_range_sync(self, since: datetime, until: datetime) -> list[int]:
        """Return MMSIs whose very first sighting falls in the given window."""
        res = (
            self._db.table("vessels")
            .select("mmsi")
            .gte("first_seen", since.isoformat())
            .lte("first_seen", until.isoformat())
            .execute()
        )
        return [r["mmsi"] for r in (res.data or [])]

    async def first_seen_in_range(self, since: datetime, until: datetime) -> list[int]:
        try:
            return await asyncio.to_thread(self._first_seen_in_range_sync, since, until)
        except Exception as exc:
            logger.error("first_seen_in_range failed: %s", exc)
            return []
