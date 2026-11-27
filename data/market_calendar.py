"""The days the US stock market is shut on a weekday.

New York Stock Exchange full closures, as the exchange publishes them. Early
closes (the day after Thanksgiving, Christmas Eve) are sessions and are not
here. Extend the list before it runs out: `runs_out()` says when, and the
nightly says so in its log 45 days ahead.

The nightly's gate keeps its own copy of these dates in bash, because it runs
before the repository is checked out. tools/test_calendar.py fails if the two
lists ever differ.

This exists because on 2026-11-27, the night after Thanksgiving, the gate took
the holiday for a session nobody had published yet, rebuilt Wednesday's
edition for forty minutes and posted it to Discord a second time.
"""
from __future__ import annotations

import datetime as dt

HOLIDAYS: frozenset[dt.date] = frozenset(dt.date.fromisoformat(d) for d in (
    # 2026
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    # 2027
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
))


def is_session(day: dt.date) -> bool:
    return day.weekday() < 5 and day not in HOLIDAYS


def previous_session(day: dt.date) -> dt.date:
    """`day` itself when it trades, else the last day before it that did."""
    while not is_session(day):
        day -= dt.timedelta(days=1)
    return day


def next_session(day: dt.date) -> dt.date:
    """The first trading day after `day`."""
    day += dt.timedelta(days=1)
    while not is_session(day):
        day += dt.timedelta(days=1)
    return day


def runs_out() -> dt.date:
    """The last day the list covers: the end of its last year."""
    return dt.date(max(d.year for d in HOLIDAYS), 12, 31)
