"""
APScheduler jobs for daily and weekly Telegram reports.

Schedules:
  - Daily:  23:59 local time every day.
  - Weekly: 23:59 local time every Sunday.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ais_notify.config import Config
from ais_notify.db.repository import Repository
from ais_notify.notify.base import Notifier
from ais_notify.notify.formatter import format_daily_stats, format_weekly_stats
from ais_notify.stats.queries import build_daily_stats, build_weekly_stats

logger = logging.getLogger(__name__)


async def _run_daily_report(repo: Repository, notifier: Notifier, tz: pytz.BaseTzInfo) -> None:
    now_local = datetime.now(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    since_utc = start_local.astimezone(timezone.utc)
    until_utc = now_local.astimezone(timezone.utc)

    logger.info("Running daily stats: %s → %s", since_utc, until_utc)
    summary = await repo.stats_summary(since_utc, until_utc)
    new_mmsis = await repo.first_seen_in_range(since_utc, until_utc)

    stats = build_daily_stats(summary, new_mmsis, now_local.strftime("%A, %d %b %Y"), tz=tz)
    message = format_daily_stats(stats)
    await notifier.send_message(message)
    logger.info("Daily report sent (%d sightings, %d unique)", stats["total_sightings"], stats["unique_vessels"])


async def _run_weekly_report(repo: Repository, notifier: Notifier, tz: pytz.BaseTzInfo) -> None:
    now_local = datetime.now(tz)
    start_local = (now_local - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

    since_utc = start_local.astimezone(timezone.utc)
    until_utc = now_local.astimezone(timezone.utc)

    logger.info("Running weekly stats: %s → %s", since_utc, until_utc)
    summary = await repo.stats_summary(since_utc, until_utc)
    daily_counts = await repo.daily_sighting_counts(since_utc, until_utc)
    new_mmsis = await repo.first_seen_in_range(since_utc, until_utc)

    week_label = f"{start_local.strftime('%d %b')} – {now_local.strftime('%d %b %Y')}"
    stats = build_weekly_stats(summary, daily_counts, new_mmsis, week_label, tz=tz)
    message = format_weekly_stats(stats)
    await notifier.send_message(message)
    logger.info("Weekly report sent (%d sightings)", stats["total_sightings"])


def create_scheduler(config: Config, repo: Repository, notifier: Notifier) -> AsyncIOScheduler:
    tz = pytz.timezone(config.timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        _run_daily_report,
        trigger="cron",
        hour=23,
        minute=59,
        id="daily_report",
        kwargs={"repo": repo, "notifier": notifier, "tz": tz},
        replace_existing=True,
    )

    scheduler.add_job(
        _run_weekly_report,
        trigger="cron",
        day_of_week="sun",
        hour=23,
        minute=59,
        id="weekly_report",
        kwargs={"repo": repo, "notifier": notifier, "tz": tz},
        replace_existing=True,
    )

    return scheduler
