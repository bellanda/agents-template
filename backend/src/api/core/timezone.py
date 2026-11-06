"""Store calendar time zone: the single source for "which DAY is it" (copy to `api/core/timezone.py`).

Every timestamp is stored in UTC (`TIMESTAMPTZ` + `datetime.now(UTC)`) and stays that way. What can
NOT run in UTC is the cut by DAY: "sales today", "best month", "orders of the day", "leads of the
day" are questions of the store calendar, not of the server clock.

The difference shows from 21:00 to midnight: at 22:00 in São Paulo it is already the next day in
UTC, so `sold_at::date` and `date_trunc('month', sold_at)` put the sale on the wrong day (sometimes
the wrong MONTH). The error is silent (the number lands in the next column) and disappears in the
morning, so it looks like flakiness instead of a bug. Incident 2026-11-05 (emporion): dinner-peak
orders counted for the next day in `/orders/stats` and the daily report.

Rules (guarded by `tests/test_timezone_guard.py` + the UTC+14 calendar canary of the test suite):
1. A day/month WINDOW is computed in Python in local time and sent to Postgres as a UTC half-open
   range: `created_at >= $start AND created_at < $end` with `local_day_bounds_utc(day)` (index
   friendly). A day/month BUCKET converts explicitly: `(col AT TIME ZONE 'America/Sao_Paulo')::date`
   or `date_trunc('month', col AT TIME ZONE $n)` — `local_date_sql(col)` builds the first.
2. "Today" is `local_today(now)`, never `date.today()` (host zone) nor `datetime.now(UTC).date()`
   (UTC day). `now` is injectable so jobs and tests pin the clock.
3. In tests the seeded date comes from the SAME zone the query compares in (rules/tests.md).

Brazil has no DST since 2019, but this is `ZoneInfo`, not a fixed -3h offset, on purpose: if DST
comes back the math stays right without anyone hunting offsets in the code.
Central source: Config Files/agents/skills/database/references/local-time/timezone.py.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any, Final
from zoneinfo import ZoneInfo

LOCAL_TZ_NAME: Final = "America/Sao_Paulo"
LOCAL_TZ: Final = ZoneInfo(LOCAL_TZ_NAME)


def store_tz(org: Mapping[str, Any] | None = None) -> ZoneInfo:
    """Time zone of a store's calendar — the ONLY seam to change when stores outside
    America/Sao_Paulo (MT/MS are UTC-4) arrive: read the org's tz here and every caller follows.

    `org` is unused today (every store is São Paulo time); callers pass it anyway so adding the
    column later does not touch them.
    """
    return LOCAL_TZ


def local_today(now: dt.datetime | None = None) -> dt.date:
    """Store-local "today"; `now` (aware) is injectable for jobs and tests."""
    return (now or dt.datetime.now(dt.UTC)).astimezone(LOCAL_TZ).date()


def local_day_bounds_utc(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """UTC `[start, end)` of the store-local `day` — compare `col >= start AND col < end`."""
    start = dt.datetime.combine(day, dt.time.min, tzinfo=LOCAL_TZ)
    return start.astimezone(dt.UTC), (start + dt.timedelta(days=1)).astimezone(dt.UTC)


def local_date_sql(column: str) -> str:
    """SQL expression for the store-local date of a TIMESTAMPTZ column. `column` must be a
    constant identifier from the calling module (never request data): it is interpolated."""
    return f"({column} AT TIME ZONE '{LOCAL_TZ_NAME}')::date"
