"""Protocol for vessel enrichment providers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ais_notify.models import Vessel, VesselSignal


@runtime_checkable
class EnrichmentProvider(Protocol):
    """
    A provider that adds or updates fields on a Vessel.

    Providers are called in order; later providers can overwrite fields
    set by earlier ones. Return the same vessel instance (mutate in-place).
    """

    async def enrich(self, vessel: Vessel, signal: VesselSignal) -> Vessel:
        """Enrich *vessel* using data from *signal* and/or external sources."""
        ...
