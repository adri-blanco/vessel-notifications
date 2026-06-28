"""Geographic geofence — point-in-polygon via ray-casting.

Configure with the GEOFENCE_POLYGON environment variable as semicolon-separated
lat,lon pairs that trace the boundary of the area you care about:

    GEOFENCE_POLYGON=41.385,2.173;41.390,2.180;41.395,2.175;41.388,2.168

At least 3 points are required (a triangle is the minimum polygon).
Points are connected in order; the polygon closes automatically.

When GEOFENCE_POLYGON is not set every signal is accepted (no filtering).
When it IS set, signals with no position are rejected because their location
cannot be verified.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Internal type: ordered list of (lat, lon) vertices
_Polygon = list[tuple[float, float]]


def _parse_polygon(raw: str) -> _Polygon:
    """Parse ``"lat,lon;lat,lon;..."`` into a list of (lat, lon) tuples."""
    points: _Polygon = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            lat_s, lon_s = part.split(",", 1)
            points.append((float(lat_s.strip()), float(lon_s.strip())))
        except ValueError as exc:
            raise ValueError(
                f"Invalid GEOFENCE_POLYGON point {part!r}: expected 'lat,lon'"
            ) from exc
    if len(points) < 3:
        raise ValueError(
            f"GEOFENCE_POLYGON must define at least 3 points, got {len(points)}"
        )
    return points


def _point_in_polygon(lat: float, lon: float, polygon: _Polygon) -> bool:
    """Ray-casting algorithm — O(n), no external dependencies required."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


class Geofence:
    """Polygon-based geofence filter.

    When *polygon* is ``None`` the fence is disabled and every position is
    accepted.  Instantiate via :meth:`from_env` to read from the environment.
    """

    def __init__(self, polygon: _Polygon | None = None) -> None:
        self._polygon = polygon

    @property
    def active(self) -> bool:
        return self._polygon is not None

    @classmethod
    def from_env(cls) -> "Geofence":
        raw = os.getenv("GEOFENCE_POLYGON", "").strip()
        if not raw:
            logger.debug("GEOFENCE_POLYGON not set — accepting all positions")
            return cls(polygon=None)
        polygon = _parse_polygon(raw)
        logger.info(
            "Geofence active: %d-point polygon — %s",
            len(polygon),
            " → ".join(f"({lat:.4f}, {lon:.4f})" for lat, lon in polygon),
        )
        return cls(polygon=polygon)

    def allows(self, lat: float | None, lon: float | None) -> bool:
        """Return *True* if the position is inside the geofence.

        Always returns *True* when the fence is inactive.
        Returns *False* when the fence is active but position is unknown (no
        lat/lon available), because the vessel's location cannot be verified.
        """
        if not self.active:
            return True
        if lat is None or lon is None:
            return False
        assert self._polygon is not None  # narrowing for type checker
        return _point_in_polygon(lat, lon, self._polygon)
