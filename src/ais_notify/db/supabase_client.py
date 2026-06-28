"""Supabase client singleton."""

from __future__ import annotations

import logging
from functools import lru_cache

from supabase import create_client, Client

from ais_notify.config import Config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client(url: str, key: str) -> Client:
    logger.info("Initialising Supabase client for %s", url)
    return create_client(url, key)


def get_supabase(config: Config) -> Client:
    return get_client(config.supabase_url, config.supabase_key)
