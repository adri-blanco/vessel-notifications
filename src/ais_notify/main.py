"""
Entry point — wires all components together and runs the event loop.

Usage:
    python -m ais_notify.main
    # or, after pip install -e .:
    ais-notify
"""

from __future__ import annotations

import asyncio
import logging
import signal as posix_signal
import sys

from ais_notify.config import load_config
from ais_notify.db.repository import Repository
from ais_notify.db.supabase_client import get_supabase
from ais_notify.decode import AISDecoder
from ais_notify.dedup import DedupCache
from ais_notify.geofence import Geofence
from ais_notify.handler import SignalHandler
from ais_notify.notify.telegram import TelegramNotifier
from ais_notify.sources.base import AISSource
from ais_notify.stats.scheduler import create_scheduler


def _build_source(config) -> AISSource:
    """Factory: return the correct AISSource for the configured AIS_SOURCE value."""
    src = config.ais_source
    if src == "udp":
        from ais_notify.sources.udp_source import UDPSource
        return UDPSource(config.ais_udp_host, config.ais_udp_port)
    if src == "tcp":
        from ais_notify.sources.tcp_source import TCPSource
        return TCPSource(config.ais_tcp_host, config.ais_tcp_port)
    if src == "serial":
        from ais_notify.sources.serial_source import SerialSource
        return SerialSource(config.ais_serial_port, config.ais_serial_baud)
    if src == "file":
        from ais_notify.sources.file_source import FileSource
        return FileSource(config.ais_file_path, loop=config.ais_file_loop)
    raise ValueError(f"Unknown AIS_SOURCE: {src!r}. Choose: udp | tcp | serial | file")


async def _main() -> None:
    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting AIS Notify (source=%s)", config.ais_source)

    # Build components
    supabase = get_supabase(config)
    repo = Repository(supabase)
    notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
    dedup = DedupCache(config.dedup_window_seconds)
    geofence = Geofence.from_env()
    source = _build_source(config)
    decoder = AISDecoder(source)
    handler = SignalHandler(repo=repo, notifier=notifier, dedup=dedup, geofence=geofence)

    # Scheduler for daily/weekly reports
    scheduler = create_scheduler(config, repo, notifier)
    scheduler.start()
    logger.info("Scheduler started (tz=%s)", config.timezone)

    # Periodic dedup cache eviction (every 10 minutes)
    async def _evict_loop() -> None:
        while True:
            await asyncio.sleep(600)
            dedup.evict_expired()

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_signal(*_) -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (posix_signal.SIGINT, posix_signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    evict_task = asyncio.create_task(_evict_loop())

    # Main AIS ingestion loop
    async def _ingest() -> None:
        msg_count = 0
        async for signal in decoder.iter_signals():
            if stop_event.is_set():
                break
            await handler.handle(signal)
            msg_count += 1
            if msg_count % 100 == 0:
                logger.info("Processed %d AIS messages", msg_count)

    ingest_task = asyncio.create_task(_ingest())

    try:
        await stop_event.wait()
    finally:
        ingest_task.cancel()
        evict_task.cancel()
        try:
            await ingest_task
        except asyncio.CancelledError:
            pass
        try:
            await evict_task
        except asyncio.CancelledError:
            pass
        scheduler.shutdown(wait=False)
        await source.close()
        logger.info("AIS Notify stopped cleanly")


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logging.getLogger(__name__).critical("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
