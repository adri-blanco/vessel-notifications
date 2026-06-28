"""
Photo enrichment provider — optional, disabled by default.

Designed as a pluggable slot. Currently ships as a stub that does nothing.
To enable:
  1. Implement _lookup_photo() to call your preferred source.
  2. Set AIS_PHOTO_ENRICHMENT=true in .env.

Supported back-ends (to be implemented):
  - Wikidata/Wikipedia: free, covers notable/named ships by IMO.
  - MarineTraffic / Datalastic / VesselFinder: requires a paid API key.
  - VesselAPI: from ~$15/mo, add AIS_VESSEL_API_KEY to .env.
"""

from __future__ import annotations

import logging
import os

from ais_notify.models import Vessel, VesselSignal

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("AIS_PHOTO_ENRICHMENT", "false").lower() == "true"
_API_KEY = os.getenv("AIS_VESSEL_API_KEY", "")  # for paid providers


async def _lookup_photo_wikidata(imo: int) -> str | None:
    """
    Query Wikidata for a ship photo by IMO number.
    Returns the Wikimedia Commons image URL or None.
    """
    try:
        import aiohttp

        sparql = f"""
        SELECT ?image WHERE {{
          ?ship wdt:P458 "{imo}" .
          ?ship wdt:P18 ?image .
        }} LIMIT 1
        """
        url = "https://query.wikidata.org/sparql"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params={"query": sparql, "format": "json"},
                headers={"User-Agent": "ais-notify/0.1"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                data = await resp.json()
                bindings = data.get("results", {}).get("bindings", [])
                if bindings:
                    raw_url: str = bindings[0]["image"]["value"]
                    # Convert to thumbnail for Telegram (800px wide)
                    filename = raw_url.split("/")[-1]
                    return (
                        f"https://commons.wikimedia.org/wiki/Special:FilePath/"
                        f"{filename}?width=800"
                    )
    except Exception as exc:
        logger.debug("Wikidata photo lookup failed for IMO %d: %s", imo, exc)
    return None


class PhotoEnricher:
    """
    Populates vessel.photo_url if a photo can be found.

    No-ops when AIS_PHOTO_ENRICHMENT != 'true' or the vessel already has a photo.
    """

    async def enrich(self, vessel: Vessel, signal: VesselSignal) -> Vessel:
        if not _ENABLED:
            return vessel
        if vessel.photo_url:
            return vessel

        if vessel.imo:
            photo = await _lookup_photo_wikidata(vessel.imo)
            if photo:
                vessel.photo_url = photo
                logger.info("Photo found for MMSI %d (IMO %d): %s", vessel.mmsi, vessel.imo, photo)

        return vessel


async def run_enrichment_chain(
    vessel: Vessel,
    signal: VesselSignal,
    providers: list,
) -> Vessel:
    """Apply each provider in sequence and return the enriched vessel."""
    for provider in providers:
        vessel = await provider.enrich(vessel, signal)
    return vessel
