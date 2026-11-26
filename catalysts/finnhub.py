"""The day's earnings figures from Finnhub's calendar.

Why a second source for something Yahoo already gives: timing and breadth.
Yahoo's per-company earnings table fills in the reported figure hours after
the release, one request a company, and has no revenue at all. Finnhub's
calendar is one request for the whole day, and each company's row carries
earnings per share and revenue, each against its estimate, soon after the
print. Market Desk has read the same calendar for months.

It needs a free key, FINNHUB_API_KEY. Without one everything here returns
nothing and the reporters run reads Yahoo alone, as it did before.

The key is sent in a header, never in the address, so it cannot end up in a
log line that prints a URL.
"""
from __future__ import annotations

import collections
import datetime as dt
import logging
import os

import requests

log = logging.getLogger(__name__)

URL = "https://finnhub.io/api/v1/calendar/earnings"
TIMEOUT = 30
AGENT = "tape-research"

#: What happened to every request made in this process.
OUTCOMES: "collections.Counter[str]" = collections.Counter()

# When in the day each of Finnhub's labels puts a report, as a New York time
# the reporters run can sort by: before the open, during the session, after
# the close. The exact minute is not known and is not claimed.
HOURS = {"bmo": dt.time(7, 0), "dmh": dt.time(12, 0), "amc": dt.time(16, 5)}


def key() -> str:
    return (os.environ.get("FINNHUB_API_KEY") or "").strip()


def enabled() -> bool:
    return bool(key())


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def surprise(actual: float | None, estimate: float | None) -> float | None:
    """How far the figure landed from the estimate, in per cent of the
    estimate's size. None when either is missing or the estimate is zero."""
    if actual is None or estimate is None or estimate == 0:
        return None
    return round(100.0 * (actual - estimate) / abs(estimate), 1)


def parse(payload: dict, day: dt.date) -> dict[str, dict]:
    """The calendar's rows for `day`, by ticker. Pure, so it can be tested."""
    out: dict[str, dict] = {}
    for row in (payload or {}).get("earningsCalendar") or []:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or str(row.get("date") or "") != day.isoformat():
            continue
        eps, estimate = _number(row.get("epsActual")), _number(row.get("epsEstimate"))
        revenue = _number(row.get("revenueActual"))
        revenue_estimate = _number(row.get("revenueEstimate"))
        # A revenue of zero is a row not filled in yet, not a company with
        # no sales.
        revenue = revenue if revenue else None
        revenue_estimate = revenue_estimate if revenue_estimate else None
        out[symbol] = {
            "hour": HOURS.get(str(row.get("hour") or "").lower()),
            "eps": eps, "estimate": estimate,
            "surprise_pct": surprise(eps, estimate),
            "revenue": revenue, "revenue_estimate": revenue_estimate,
            "revenue_surprise_pct": surprise(revenue, revenue_estimate),
        }
    return out


def calendar(day: dt.date) -> dict[str, dict]:
    """Everybody Finnhub has reporting on `day`. {} without a key, and {}
    when it does not answer: a reporters run must never fail on this."""
    token = key()
    if not token:
        OUTCOMES["no_key"] += 1
        return {}
    try:
        response = requests.get(
            URL, params={"from": day.isoformat(), "to": day.isoformat()},
            headers={"X-Finnhub-Token": token, "User-Agent": AGENT},
            timeout=TIMEOUT)
        if response.status_code != 200:
            OUTCOMES[f"http_{response.status_code}"] += 1
            return {}
        found = parse(response.json(), day)
        OUTCOMES["ok"] += 1
        return found
    except (requests.RequestException, ValueError) as exc:
        OUTCOMES["error"] += 1
        log.debug("finnhub calendar %s: %s", day, type(exc).__name__)
        return {}


def complete(row: dict | None) -> bool:
    """Whether a calendar row is enough for a line on its own: when in the
    day, and the reported figure."""
    return bool(row and row.get("hour") is not None and row.get("eps") is not None)


def merged(yahoo: dict | None, finnhub: dict | None) -> dict | None:
    """One company's line for the day from both sources.

    Yahoo's hour is an actual time and is kept when there is one. A figure
    comes from whichever has it, Finnhub first because it has it sooner, and
    the estimate is taken from the same source as the figure so a surprise
    is never one source's actual against the other's estimate. Revenue is
    Finnhub's alone.
    """
    if not yahoo and not finnhub:
        return None
    yahoo, finnhub = yahoo or {}, finnhub or {}
    hour = yahoo.get("hour") if yahoo.get("hour") is not None else finnhub.get("hour")
    if hour is None:
        return None
    figures = finnhub if finnhub.get("eps") is not None else yahoo
    if figures.get("eps") is None:
        # Nobody has the figure yet. An estimate alone is still worth a line.
        figures = finnhub if finnhub.get("estimate") is not None else yahoo
    return {
        "hour": hour,
        "eps": figures.get("eps"), "estimate": figures.get("estimate"),
        "surprise_pct": figures.get("surprise_pct"),
        "revenue": finnhub.get("revenue"),
        "revenue_estimate": finnhub.get("revenue_estimate"),
        "revenue_surprise_pct": finnhub.get("revenue_surprise_pct"),
    }
