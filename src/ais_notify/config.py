"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set.")
    return value


def _get(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Config:
    # Supabase
    supabase_url: str
    supabase_key: str

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str

    # AIS source selection
    ais_source: str  # udp | tcp | serial | file

    # UDP source
    ais_udp_host: str
    ais_udp_port: int

    # TCP source
    ais_tcp_host: str
    ais_tcp_port: int

    # Serial source
    ais_serial_port: str
    ais_serial_baud: int

    # File source
    ais_file_path: Path
    ais_file_loop: bool

    # Behaviour
    dedup_window_seconds: int
    timezone: str
    log_level: str


def load_config() -> Config:
    return Config(
        supabase_url=_require("SUPABASE_URL"),
        supabase_key=_require("SUPABASE_KEY"),
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require("TELEGRAM_CHAT_ID"),
        ais_source=_get("AIS_SOURCE", "udp").lower(),
        ais_udp_host=_get("AIS_UDP_HOST", "127.0.0.1"),
        ais_udp_port=int(_get("AIS_UDP_PORT", "10110")),
        ais_tcp_host=_get("AIS_TCP_HOST", "127.0.0.1"),
        ais_tcp_port=int(_get("AIS_TCP_PORT", "10110")),
        ais_serial_port=_get("AIS_SERIAL_PORT", "/dev/ttyAMA0"),
        ais_serial_baud=int(_get("AIS_SERIAL_BAUD", "38400")),
        ais_file_path=Path(_get("AIS_FILE_PATH", "tests/sample.nmea")),
        ais_file_loop=_get("AIS_FILE_LOOP", "false").lower() == "true",
        dedup_window_seconds=int(_get("DEDUP_WINDOW_SECONDS", "300")),
        timezone=_get("TIMEZONE", "UTC"),
        log_level=_get("LOG_LEVEL", "INFO"),
    )
