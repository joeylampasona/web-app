"""Where a setup sits in its life: forming, fresh, climbing, or played out.

played_out is published, never filtered. A site that only shows the ones that
worked is a site with nothing to check it against.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from data.types import Bar

FORMING = "forming"
FRESH = "fresh_breakout"
CLIMBING = "climbing"
PLAYED_OUT = "played_out"

ORDER = (FORMING, FRESH, CLIMBING, PLAYED_OUT)

LABELS = {
    FORMING: "Forming",
    FRESH: "Fresh breakouts",
    CLIMBING: "Climbing",
    PLAYED_OUT: "Played out",
}

STOP_PCT = 8.0            # the trailing-stop convention the stage rules assume


@dataclass
class StageResult:
    stage: str
    breakout_date: dt.date | None = None
    sessions_since: int | None = None
    outcome_pct: float | None = None
    exit_reason: str = ""


def classify(bars: list[Bar], sma50: list[float | None], breakout_idx: int | None,
             fresh_sessions: int, today_year: int) -> StageResult | None:
    """None means the structure has nothing left to say — it broke out in an
    earlier calendar year and has already finished."""
    n = len(bars)
    if breakout_idx is None:
        return StageResult(FORMING)

    since = n - 1 - breakout_idx
    entry = bars[breakout_idx].close
    breakout_date = bars[breakout_idx].date

    if since <= fresh_sessions:
        return StageResult(FRESH, breakout_date, since,
                           100.0 * (bars[-1].close / entry - 1.0) if entry else None)

    stopped_at: int | None = None
    for i in range(breakout_idx + 1, n):
        if entry and bars[i].close <= entry * (1.0 - STOP_PCT / 100.0):
            stopped_at = i
            break
        line = sma50[i]
        if line and bars[i].close < line:
            stopped_at = i
            break

    if stopped_at is None:
        return StageResult(CLIMBING, breakout_date, since,
                           100.0 * (bars[-1].close / entry - 1.0) if entry else None)

    exit_price = bars[stopped_at].close
    outcome = 100.0 * (exit_price / entry - 1.0) if entry else None
    reason = ("stopped out" if entry and exit_price <= entry * (1.0 - STOP_PCT / 100.0)
              else "trailed out")
    if breakout_date.year != today_year:
        return None
    return StageResult(PLAYED_OUT, breakout_date, since, outcome, reason)
