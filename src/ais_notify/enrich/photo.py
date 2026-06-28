"""
Photo + name enrichment provider — optional, disabled by default.

Set AIS_PHOTO_ENRICHMENT=true in .env to enable.

Lookup strategy (tried in order):
  1. VesselFinder scrape — broadest free coverage; works by MMSI alone (no IMO
     required), so it covers barges, small craft, and inland vessels too.
     Also extracts the vessel name from the page <h1> when AIS hasn't supplied one.
  2. Wikidata by IMO    — precise, works for registered named vessels.
  3. Wikidata by name  — last-chance fallback when there is no IMO.

Caching:
  Successful results (photo_url, name) are persisted to the DB so subsequent
  sightings skip all HTTP calls immediately.
  Failed attempts are recorded in vessel.info["photo_attempted_at"]; the enricher
  will not retry for AIS_PHOTO_RECHECK_DAYS (default 30) to avoid hammering APIs
  on every sighting of a vessel that has no publicly available photo or name.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from ais_notify.models import Vessel, VesselSignal

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("AIS_PHOTO_ENRICHMENT", "false").lower() == "true"
_PHOTO_RECHECK_DAYS = int(os.getenv("AIS_PHOTO_RECHECK_DAYS", "30"))

_WIKIDATA_URL = "https://query.wikidata.org/sparql"
_WIKIDATA_HEADERS = {"User-Agent": "ais-notify/0.1 (vessel sighting notifier)"}
_WIKIDATA_TIMEOUT = 6

_VF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
_VF_TIMEOUT = 8

# VesselFinder ship-photo CDN token, server-rendered in the page HTML:
#   src="https://static.vesselfinder.net/ship-photo/{imo}-{mmsi}-{hash}/1?v1"
_SHIP_PHOTO_RE = re.compile(r'ship-photo/(\d+-\d+-[a-f0-9]+/\d+[^"\'<>\s]*)')

# Vessel name in the page <h1> (also present in <title> as "{name}, {type} - …")
_H1_RE = re.compile(r'<h1[^>]*>([^<]+)</h1>')


def _wikimedia_thumbnail(raw_url: str, width: int = 800) -> str:
    filename = raw_url.split("/")[-1]
    # Wikidata URLs may already be percent-encoded; normalise before re-encoding
    # to avoid double-encoding (e.g. space → %20 → %2520).
    filename = urllib.parse.quote(urllib.parse.unquote(filename))
    return (
        f"https://commons.wikimedia.org/wiki/Special:FilePath/"
        f"{filename}?width={width}"
    )


async def _scrape_vessel_finder(mmsi: int) -> tuple[str | None, str | None]:
    """
    Fetch the VesselFinder vessel details page and extract photo URL and name.

    Returns (photo_url, name). Either or both may be None.

    Photo: served server-side as
        <img class="main-photo"
             src="https://static.vesselfinder.net/ship-photo/{imo}-{mmsi}-{hash}/1?v1">
    Name: in the page <h1> tag (e.g. <h1>EMS COURAGE</h1>).
    When a vessel is unknown to VesselFinder the page still returns 200 but
    both tokens are absent.
    """
    url = f"https://www.vesselFinder.com/vessels/details/{mmsi}"
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=_VF_HEADERS,
                timeout=aiohttp.ClientTimeout(total=_VF_TIMEOUT),
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "VesselFinder returned HTTP %d for MMSI %d", resp.status, mmsi
                    )
                    return None, None
                html = await resp.text()

        photo_url: str | None = None
        name: str | None = None

        photo_match = _SHIP_PHOTO_RE.search(html)
        if photo_match:
            photo_url = f"https://static.vesselfinder.net/ship-photo/{photo_match.group(1)}"

        name_match = _H1_RE.search(html)
        if name_match:
            raw_name = name_match.group(1).strip()
            # Sanity-check: reject page-level headings like "VesselFinder" that
            # appear when the MMSI isn't in their database.
            if raw_name and raw_name.lower() not in {"vesselfinder", "vessel finder"}:
                name = raw_name.upper()  # normalise to AIS-style uppercase

        return photo_url, name

    except Exception as exc:
        logger.warning("VesselFinder scrape failed for MMSI %d: %s", mmsi, exc)
    return None, None


async def _wikidata_query(sparql: str) -> str | None:
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                _WIKIDATA_URL,
                params={"query": sparql, "format": "json"},
                headers=_WIKIDATA_HEADERS,
                timeout=aiohttp.ClientTimeout(total=_WIKIDATA_TIMEOUT),
            ) as resp:
                data = await resp.json()
                bindings = data.get("results", {}).get("bindings", [])
                if bindings:
                    return bindings[0]["image"]["value"]
    except Exception as exc:
        logger.debug("Wikidata query failed: %s", exc)
    return None


async def _lookup_by_imo(imo: int) -> str | None:
    sparql = f"""
    SELECT ?image WHERE {{
      ?ship wdt:P458 "{imo}" .
      ?ship wdt:P18 ?image .
    }} LIMIT 1
    """
    raw = await _wikidata_query(sparql)
    return _wikimedia_thumbnail(raw) if raw else None


async def _lookup_by_name(name: str) -> str | None:
    """
    Try both the raw AIS name (uppercase) and title-cased form.
    Constrained to watercraft (Q1229765) to avoid false matches against
    geographic names, albums, or anything else sharing the vessel's name.
    """
    candidates = list(dict.fromkeys([name, name.title()]))  # preserve order, dedupe
    for candidate in candidates:
        escaped = candidate.replace('"', '\\"')
        sparql = f"""
        SELECT ?image WHERE {{
          ?ship wdt:P31/wdt:P279* wd:Q1229765 .
          ?ship wdt:P18 ?image .
          {{ ?ship rdfs:label "{escaped}"@en . }}
          UNION
          {{ ?ship skos:altLabel "{escaped}"@en . }}
        }} LIMIT 1
        """
        raw = await _wikidata_query(sparql)
        if raw:
            return _wikimedia_thumbnail(raw)
    return None


def _recently_attempted(vessel: Vessel) -> bool:
    """Return True if a photo lookup was tried within the recheck window."""
    ts_str = vessel.info.get("photo_attempted_at")
    if not ts_str:
        return False
    try:
        attempted = datetime.fromisoformat(ts_str)
        return datetime.now(timezone.utc) - attempted < timedelta(days=_PHOTO_RECHECK_DAYS)
    except ValueError:
        return False


class PhotoEnricher:
    """
    Populates vessel.photo_url and vessel.name (when missing) from external sources.

    Skips when:
    - AIS_PHOTO_ENRICHMENT != 'true'
    - vessel already has both photo_url and name (fully cached from DB)
    - a lookup was attempted within the last AIS_PHOTO_RECHECK_DAYS days
      (stored in vessel.info["photo_attempted_at"])
    """

    async def enrich(self, vessel: Vessel, signal: VesselSignal) -> Vessel:
        if not _ENABLED:
            return vessel
        # Skip only when everything we could fill in is already set
        if vessel.photo_url and vessel.name:
            return vessel
        if _recently_attempted(vessel):
            return vessel

        photo: str | None = None

        # 1. VesselFinder — broadest coverage; also supplies the vessel name
        photo, vf_name = await _scrape_vessel_finder(vessel.mmsi)
        if photo:
            logger.info("Photo found via VesselFinder for MMSI %d: %s", vessel.mmsi, photo)
        if vf_name and not vessel.name:
            vessel.name = vf_name
            logger.info("Name found via VesselFinder for MMSI %d: %r", vessel.mmsi, vf_name)

        # 2. Wikidata by IMO
        if not photo and vessel.imo:
            photo = await _lookup_by_imo(vessel.imo)
            if photo:
                logger.info(
                    "Photo found via Wikidata IMO for MMSI %d (IMO %d): %s",
                    vessel.mmsi, vessel.imo, photo,
                )

        # 3. Wikidata by name
        if not photo and vessel.name:
            photo = await _lookup_by_name(vessel.name)
            if photo:
                logger.info(
                    "Photo found via Wikidata name for MMSI %d (%r): %s",
                    vessel.mmsi, vessel.name, photo,
                )

        if photo:
            vessel.photo_url = photo

        # Always record the attempt so we don't retry on every sighting
        vessel.info["photo_attempted_at"] = datetime.now(timezone.utc).isoformat()

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
