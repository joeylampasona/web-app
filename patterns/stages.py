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

LONG = "long"
SHORT = "short"

LABELS = {
    FORMING: "Forming",
    FRESH: "Fresh breakouts",
    CLIMBING: "Climbing",
    PLAYED_OUT: "Played out",
}

# The same four stages, named for a shape that resolves downward.
#
# The stage KEYS are shared on purpose — every count, diff and filter on the
# site is written against them, and a second vocabulary would have to be
# threaded through all of it. Only the words change, and they change per screen
# because the published screen file already carries its own labels. Calling a
# bear flag's resolution "Fresh breakouts" and its follow-through "Climbing"
# would have been the site describing a falling stock as rising.
SHORT_LABELS = {
    FORMING: "Forming",
    FRESH: "Fresh breakdowns",
    CLIMBING: "Falling",
    PLAYED_OUT: "Played out",
}

STOP_PCT = 8.0            # the trailing-stop convention the stage rules assume


def labels_for(direction: str) -> dict[str, str]:
    return SHORT_LABELS if direction == SHORT else LABELS


def help_for(direction: str, year: int) -> dict[str, str]:
    if direction == SHORT:
        return {
            FORMING: "resting before a breakdown",
            FRESH: "lost it in the last 5 sessions",
            CLIMBING: "broke down earlier, still falling",
            PLAYED_OUT: f"{year} breakdowns, stopped or trailed out",
        }
    return {
        FORMING: "resting before a breakout",
        FRESH: "cleared it in the last 5 sessions",
        CLIMBING: "broke out earlier, still rising",
        PLAYED_OUT: f"{year} breakouts, stopped or trailed out",
    }


@dataclass
class StageResult:
    stage: str
    breakout_date: dt.date | None = None
    sessions_since: int | None = None
    outcome_pct: float | None = None
    exit_reason: str = ""


def _progress(entry: float, price: float, direction: str) -> float | None:
    """How far the setup has gone ITS way, in percent.

    Positive always means the shape did what it was read to do. For a long that
    is price rising; for a short it is price falling. Reporting a bear flag that
    fell 12% as "-12%" would have every short setup on the site look like a
    losing one at exactly the moment it worked.
    """
    if not entry:
        return None
    if direction == SHORT:
        return 100.0 * (1.0 - price / entry)
    return 100.0 * (price / entry - 1.0)


def classify(bars: list[Bar], sma50: list[float | None], breakout_idx: int | None,
             fresh_sessions: int, today_year: int,
             direction: str = LONG) -> StageResult | None:
    """None means the structure has nothing left to say — it broke out in an
    earlier calendar year and has already finished.

    `direction` inverts every test rather than only the wording. For a short
    setup the stop is price rising 8% against the entry or reclaiming the
    50-day line, which are the mirror images of the long rules and not the same
    rules with different labels.
    """
    n = len(bars)
    if breakout_idx is None:
        return StageResult(FORMING)

    since = n - 1 - breakout_idx
    entry = bars[breakout_idx].close
    breakout_date = bars[breakout_idx].date
    short = direction == SHORT

    if since <= fresh_sessions:
        return StageResult(FRESH, breakout_date, since,
                           _progress(entry, bars[-1].close, direction))

    stop_level = (entry * (1.0 + STOP_PCT / 100.0) if short
                  else entry * (1.0 - STOP_PCT / 100.0))
    stopped_at: int | None = None
    for i in range(breakout_idx + 1, n):
        if entry and ((bars[i].close >= stop_level) if short
                      else (bars[i].close <= stop_level)):
            stopped_at = i
            break
        line = sma50[i]
        # A long is trailed out by losing the 50-day; a short by reclaiming it.
        if line and ((bars[i].close > line) if short else (bars[i].close < line)):
            stopped_at = i
            break

    if stopped_at is None:
        return StageResult(CLIMBING, breakout_date, since,
                           _progress(entry, bars[-1].close, direction))

    exit_price = bars[stopped_at].close
    outcome = _progress(entry, exit_price, direction)
    hit_stop = entry and ((exit_price >= stop_level) if short
                          else (exit_price <= stop_level))
    reason = "stopped out" if hit_stop else "trailed out"
    if breakout_date.year != today_year:
        return None
    return StageResult(PLAYED_OUT, breakout_date, since, outcome, reason)
