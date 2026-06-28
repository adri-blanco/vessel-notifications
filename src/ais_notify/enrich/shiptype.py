"""
AIS ship type code -> human-readable label + emoji.

Source: ITU-R M.1371-5 Annex 8, Table 23.
"""

from __future__ import annotations

_SHIP_TYPES: dict[int, tuple[str, str]] = {
    # (label, emoji)
    0:  ("Not available", "❓"),
    # Reserved 1–19
    20: ("Wing in ground", "🛩️"),
    21: ("Wing in ground (hazardous A)", "⚠️"),
    22: ("Wing in ground (hazardous B)", "⚠️"),
    23: ("Wing in ground (hazardous C)", "⚠️"),
    24: ("Wing in ground (hazardous D)", "⚠️"),
    29: ("Wing in ground (no additional info)", "🛩️"),
    30: ("Fishing", "🎣"),
    31: ("Towing", "⛴️"),
    32: ("Towing large", "⛴️"),
    33: ("Dredging / underwater ops", "⚙️"),
    34: ("Diving ops", "🤿"),
    35: ("Military ops", "⚓"),
    36: ("Sailing", "⛵"),
    37: ("Pleasure craft", "⛵"),
    40: ("High speed craft", "🚤"),
    41: ("High speed craft (hazardous A)", "⚠️"),
    42: ("High speed craft (hazardous B)", "⚠️"),
    43: ("High speed craft (hazardous C)", "⚠️"),
    44: ("High speed craft (hazardous D)", "⚠️"),
    49: ("High speed craft (no additional info)", "🚤"),
    50: ("Pilot vessel", "🚢"),
    51: ("Search and rescue", "🆘"),
    52: ("Tug", "⛴️"),
    53: ("Port tender", "⛴️"),
    54: ("Anti-pollution equipment", "♻️"),
    55: ("Law enforcement", "🚔"),
    58: ("Medical transport", "🏥"),
    59: ("Non-combatant ship (RR Resolution 18)", "🚢"),
    60: ("Passenger", "🛳️"),
    61: ("Passenger (hazardous A)", "⚠️"),
    62: ("Passenger (hazardous B)", "⚠️"),
    63: ("Passenger (hazardous C)", "⚠️"),
    64: ("Passenger (hazardous D)", "⚠️"),
    69: ("Passenger (no additional info)", "🛳️"),
    70: ("Cargo", "🚢"),
    71: ("Cargo (hazardous A)", "⚠️"),
    72: ("Cargo (hazardous B)", "⚠️"),
    73: ("Cargo (hazardous C)", "⚠️"),
    74: ("Cargo (hazardous D)", "⚠️"),
    79: ("Cargo (no additional info)", "🚢"),
    80: ("Tanker", "🛢️"),
    81: ("Tanker (hazardous A)", "⚠️"),
    82: ("Tanker (hazardous B)", "⚠️"),
    83: ("Tanker (hazardous C)", "⚠️"),
    84: ("Tanker (hazardous D)", "⚠️"),
    89: ("Tanker (no additional info)", "🛢️"),
    90: ("Other", "🚢"),
    91: ("Other (hazardous A)", "⚠️"),
    92: ("Other (hazardous B)", "⚠️"),
    93: ("Other (hazardous C)", "⚠️"),
    94: ("Other (hazardous D)", "⚠️"),
    99: ("Other (no additional info)", "🚢"),
}


def ship_type_label(code: int | None) -> str:
    """Return human-readable label for an AIS ship type code."""
    if code is None:
        return "Unknown"
    entry = _SHIP_TYPES.get(code)
    if entry:
        return entry[0]
    # Fall back to category ranges
    if 1 <= code <= 19:
        return "Reserved"
    if 20 <= code <= 29:
        return "Wing in ground"
    if 30 <= code <= 39:
        return "Special craft"
    if 40 <= code <= 49:
        return "High speed craft"
    if 50 <= code <= 59:
        return "Special vessel"
    if 60 <= code <= 69:
        return "Passenger"
    if 70 <= code <= 79:
        return "Cargo"
    if 80 <= code <= 89:
        return "Tanker"
    if 90 <= code <= 99:
        return "Other"
    return "Unknown"


def ship_type_emoji(code: int | None) -> str:
    if code is None:
        return "🚢"
    entry = _SHIP_TYPES.get(code)
    return entry[1] if entry else "🚢"
