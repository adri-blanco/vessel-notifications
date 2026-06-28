"""
Vessel direction classification based on Course Over Ground (COG).

COG is measured in degrees clockwise from True North (0° = N, 90° = E,
180° = S, 270° = W).

A vessel heading southward — COG in the arc 90° → 270° — is considered
"Arriving" (coming from the north).  A vessel heading northward — COG in
the arc 270° → 360° / 0° → 90° — is "Departing" (leaving toward the north).

Returns None when:
  - COG is not available in the AIS signal.
  - Speed (SOG) is below 0.5 knots: at very low speeds the COG reading is
    unreliable and the vessel is effectively stationary.
"""

from __future__ import annotations

ARRIVING = "Arriving"
DEPARTING = "Departing"

_MIN_SOG_KNOTS = 0.5


def classify_direction(cog: float | None, sog: float | None) -> str | None:
    """Return 'Arriving', 'Departing', or None.

    Args:
        cog: Course Over Ground in degrees (0–360). May be None.
        sog: Speed Over Ground in knots. May be None.
    """
    if cog is None:
        return None
    if sog is not None and sog < _MIN_SOG_KNOTS:
        return None

    normalized = cog % 360
    # Southward half of the compass → vessel moving toward the south → Arriving
    if 90.0 < normalized < 270.0:
        return ARRIVING
    # Northward half → vessel moving toward the north → Departing
    return DEPARTING
