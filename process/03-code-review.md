# AIS Notify — Code Review
Done with skill /grill-me

> Grilling session on the plan and initial implementation.
> These are real bugs and design problems, not nitpicks.

---

## 1. You make `get_last_sighting` twice per signal — on purpose

In `handler.handle()`, `dedup.is_duplicate()` already calls `repo.get_last_sighting(mmsi)` on a cache miss. Then on line 56, `handler` calls it **again** to populate the "last seen X ago" text for the notification. That's two DB round trips for the same timestamp for every vessel whose dedup window just expired. The return value from `is_duplicate` is thrown away. You could pass it back up and reuse it.

---

## 2. The weekly stats day sort is broken

In `queries.py` line 97:

```python
# Sort daily trend chronologically (day_key format keeps Mon < Sun)
daily_trend = sorted(day_counter.items(), key=lambda x: x[0])
```

The comment is wrong. `"%a %d"` produces `"Mon 23"`, `"Tue 24"`, etc. Sorted alphabetically: **Fri < Mon < Sat < Sun < Thu < Tue < Wed**. A Mon–Sun week would display as Fri, Mon, Sat, Sun, Thu, Tue, Wed. The weekly trend chart will be gibberish.

---

## 3. Vessel names are interpolated raw into Telegram HTML

In `formatter.py` line 58:

```python
header = f"{emoji} <b>{name}</b> {flag}"
```

AIS vessel names come from radio and contain arbitrary ASCII. A vessel named `A&B SHIPPING <2>` will produce malformed HTML. Telegram's Bot API will return an error, the message delivery silently fails inside `send_message`'s `except TelegramError`, and you lose the notification. Every user-provided string — name, callsign, destination — needs `html.escape()` before interpolation.

---

## 4. `apscheduler>=3.10` will likely install version 4 and crash at startup

APScheduler 4.x dropped `AsyncIOScheduler` entirely and rewrote the API. `scheduler.py` uses `from apscheduler.schedulers.asyncio import AsyncIOScheduler` — an import that doesn't exist in 4.x. Anyone doing a fresh install today will get 4.x (released in 2024) and the process will die immediately with `ImportError`. The requirement should be `apscheduler>=3.10,<4`.

---

## 5. The fragment buffer has no TTL — it leaks memory

In `decode.py`, incomplete multi-part messages (second part never arrives due to UDP loss) accumulate in `self._fragments` forever. In a busy port with frequent UDP drops this grows without bound. A fragment older than ~30 seconds will never complete and should be evicted.

---

## 6. A failed `upsert_vessel` silently causes the sighting to disappear

In `_persist`:

```python
async def _persist(self, vessel: Vessel, sighting: Sighting, is_first_ever: bool) -> None:
    if is_first_ever:
        # Insert vessel row first (sightings FK depends on it)
        await self._repo.upsert_vessel(vessel)
    await self._repo.insert_sighting(sighting)
```

`upsert_vessel` swallows its exception internally and returns `None` on failure. Then `insert_sighting` runs with an MMSI that was never written to the DB, hits a FK violation, and also swallows its exception. Both failures are logged at ERROR level but there is no guard, no retry, no local queue. The sighting is gone. You should at least check whether the vessel insert succeeded before attempting the sighting insert.

---

## 7. The initial decoder was written for the wrong pyais version

The first implementation used `NMEAMessage(raw_line)` — pyais 2.x API. pyais 3.x (which `requirements.txt` specifies as `>=2.9`, so 3.x is valid) takes raw bytes directly. It only came to light because the decode tests failed. The requirement `pyais>=2.9` allows installing a version whose API the code doesn't match.

---

## 8. The `busiest_hour` is UTC, not local time

Stats are triggered at 23:59 **local** time, but inside `build_daily_stats`, the hour is extracted from the raw UTC timestamp without converting to the user's timezone. If you're in UTC+2, the report will say the busiest hour is 10:00 when it was actually noon local time. Pass the timezone into the stats builder or convert timestamps before aggregating.

---

## 9. `query_sightings` loads all rows into memory for aggregation

`_query_sightings_sync` fetches every sighting row for the day into Python and then aggregates in Python. In a busy anchorage with hundreds of vessels this could easily be tens of thousands of rows. On a Raspberry Pi with 1–2 GB RAM, a busy week's report could OOM. The aggregations (unique vessels, type breakdown, hourly counts) should be SQL `GROUP BY` queries pushed down to Postgres, not Python-side iteration.

---

## 10. No `.gitignore`

There is no `.gitignore`. `.env` (with real Supabase keys and Telegram tokens), `.venv/`, and `*.pyc` files are all untracked and one `git add .` away from being committed. This is a credential leak waiting to happen on a project designed to run 24/7 on a Pi.

---

## Fixes applied

All 10 issues were fixed in the same session:

| # | Issue | Fix |
|---|-------|-----|
| 1 | Double `get_last_sighting` DB call | `DedupCache.check()` now returns `(is_dup, last_seen)` in one call; handler uses the returned timestamp directly |
| 2 | Weekly day sort alphabetical not chronological | `build_weekly_stats` stores a reference `datetime` per day label and sorts by `.date()`, not the display string |
| 3 | Vessel names not HTML-escaped → silent Telegram failures | Added `html.escape()` via `_e()` helper wrapping every user-supplied string in the formatter |
| 4 | `apscheduler>=3.10` would install APScheduler 4 (broken API) | Pinned `apscheduler>=3.10,<4` and `python-telegram-bot<23`, `supabase<3` |
| 5 | Fragment buffer memory leak on UDP packet loss | Each fragment entry now stores `(arrival_time, parts)`, evicted every 500 messages if older than 30s |
| 6 | `upsert_vessel` failure silently caused FK-violating sighting insert | `upsert_vessel` returns `bool`; `_persist` skips `insert_sighting` if vessel insert failed |
| 7 | `pyais>=2.9` allowed a version whose API the code didn't use | Pinned `pyais>=3.0,<4` |
| 8 | `busiest_hour` shown in UTC not local time | Stats builders now accept `tz` and convert UTC timestamps before computing the hour |
| 9 | `query_sightings` loaded all rows into Python for aggregation | Replaced with two SQL functions (`stats_summary`, `daily_sighting_counts`) using `GROUP BY` on Postgres |
| 10 | No `.gitignore` | Added `.gitignore` covering `.env`, `.venv/`, `__pycache__/`, etc. |
