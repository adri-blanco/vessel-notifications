"""
On-demand Telegram bot commands: /today, /week, /all.

Registers command handlers on a python-telegram-bot Application.
Commands are silently ignored when sent from any chat other than the
configured TELEGRAM_CHAT_ID, so the bot won't respond to strangers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytz
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from ais_notify.db.repository import Repository
from ais_notify.notify.formatter import format_all_stats, format_daily_stats, format_weekly_stats
from ais_notify.stats.queries import build_all_stats, build_daily_stats, build_weekly_stats

logger = logging.getLogger(__name__)

_THINKING = "⏳ Crunching the numbers…"


def _allowed(update: Update, chat_id: str) -> bool:
    return update.effective_chat is not None and str(update.effective_chat.id) == chat_id


def _make_today_handler(repo: Repository, tz: pytz.BaseTzInfo, chat_id: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _allowed(update, chat_id):
            return
        assert update.message is not None
        await update.message.reply_text(_THINKING)

        now_local = datetime.now(tz)
        since_utc = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        until_utc = now_local.astimezone(timezone.utc)

        summary = await repo.stats_summary(since_utc, until_utc)
        new_mmsis = await repo.first_seen_in_range(since_utc, until_utc)
        stats = build_daily_stats(summary, new_mmsis, now_local.strftime("%A, %d %b %Y"), tz=tz)
        await update.message.reply_text(
            format_daily_stats(stats),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    return handler


def _make_week_handler(repo: Repository, tz: pytz.BaseTzInfo, chat_id: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _allowed(update, chat_id):
            return
        assert update.message is not None
        await update.message.reply_text(_THINKING)

        now_local = datetime.now(tz)
        start_local = (now_local - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        since_utc = start_local.astimezone(timezone.utc)
        until_utc = now_local.astimezone(timezone.utc)

        summary = await repo.stats_summary(since_utc, until_utc)
        daily_counts = await repo.daily_sighting_counts(since_utc, until_utc)
        new_mmsis = await repo.first_seen_in_range(since_utc, until_utc)
        week_label = f"{start_local.strftime('%d %b')} – {now_local.strftime('%d %b %Y')}"
        stats = build_weekly_stats(summary, daily_counts, new_mmsis, week_label, tz=tz)
        await update.message.reply_text(
            format_weekly_stats(stats),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    return handler


def _make_all_handler(repo: Repository, chat_id: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _allowed(update, chat_id):
            return
        assert update.message is not None
        await update.message.reply_text(_THINKING)

        until_utc = datetime.now(timezone.utc)
        since_utc = datetime(1970, 1, 1, tzinfo=timezone.utc)

        summary = await repo.stats_summary(since_utc, until_utc)
        first_date = await repo.get_first_sighting_date()
        stats = build_all_stats(summary, first_date)
        await update.message.reply_text(
            format_all_stats(stats),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    return handler


def build_command_app(
    token: str,
    chat_id: str,
    repo: Repository,
    tz: pytz.BaseTzInfo,
) -> Application:
    """Build a Telegram Application with /today, /week, /all command handlers."""
    app: Application = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("today", _make_today_handler(repo, tz, chat_id)))
    app.add_handler(CommandHandler("week", _make_week_handler(repo, tz, chat_id)))
    app.add_handler(CommandHandler("all", _make_all_handler(repo, chat_id)))
    logger.info("Bot commands registered: /today  /week  /all")
    return app
