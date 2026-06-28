"""
AIS static data enrichment provider.

Applies the data already present in the VesselSignal (decoded from the
AIS message itself) plus ship-type labels and MMSI country lookups.
This is entirely free — no external API calls needed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ais_notify.enrich.base import EnrichmentProvider
from ais_notify.enrich.shiptype import ship_type_label
from ais_notify.enrich.mmsi import mid_lookup
from ais_notify.models import Vessel, VesselSignal


class AISStaticEnricher:
    """Applies decoded AIS static data and derived lookups to a Vessel."""

    async def enrich(self, vessel: Vessel, signal: VesselSignal) -> Vessel:
        # Copy static fields from the signal if they carry new info
        if signal.name and not vessel.name:
            vessel.name = signal.name
        if signal.imo and not vessel.imo:
            vessel.imo = signal.imo
        if signal.callsign and not vessel.callsign:
            vessel.callsign = signal.callsign
        if signal.ship_type is not None and vessel.ship_type is None:
            vessel.ship_type = signal.ship_type

        # Always (re-)derive label and country from the latest data
        if vessel.ship_type is not None and not vessel.ship_type_label:
            vessel.ship_type_label = ship_type_label(vessel.ship_type)

        if not vessel.flag_country:
            country, emoji = mid_lookup(vessel.mmsi)
            vessel.flag_country = country
            vessel.flag_emoji = emoji

        # Dimensions — only update if not already set
        if signal.length and not vessel.length_m:
            vessel.length_m = signal.length
        if signal.width and not vessel.width_m:
            vessel.width_m = signal.width
        if signal.draught and not vessel.draught:
            vessel.draught = signal.draught

        if signal.destination and not vessel.destination:
            vessel.destination = signal.destination
        if signal.eta and not vessel.eta:
            vessel.eta = signal.eta

        vessel.last_enriched = datetime.now(timezone.utc)
        return vessel
