"""Under last week's low, and back above it by the close.

Every other screen here watches a stock approach a ceiling. This one watches
a floor get broken and not stay broken. Last week's low is a price everybody
can see, so it is where the stops sit; a session that trades through it and
closes back above has taken those stops out and found nobody willing to sell
lower. On a daily chart that is the whole of what an intraday trader calls a
sweep and reclaim.

It is a fact about four prices, and it is checkable from bars alone: the
level is the lowest low of the previous calendar week of sessions, the
undercut is a low beneath it, and the reclaim is a close above it. Nothing
here is fitted.

"Previous week" is by the calendar, Monday to Friday, whatever sessions that
week had. A week shortened by a holiday is still a week, and its low is
still the low people were looking at.

The whole history of these is reconstructable, which a fitted trendline's is
not, so this screen's record can be measured from its first night.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Sequence

from data.types import Bar


def week_of(day: dt.date) -> dt.date:
    """The Monday of the calendar week a session falls in."""
    return day - dt.timedelta(days=day.weekday())


def weeks(bars: Sequence[Bar]) -> list[tuple[dt.date, int, int]]:
    """(Monday, first index, last index) for each calendar week with sessions,
    oldest first."""
    out: list[tuple[dt.date, int, int]] = []
    for index, bar in enumerate(bars):
        monday = week_of(bar.date)
        if out and out[-1][0] == monday:
            out[-1] = (monday, out[-1][1], index)
        else:
            out.append((monday, index, index))
    return out


def prior_week(bars: Sequence[Bar]) -> dict | None:
    """The previous calendar week's high and low, as the last bar sees them.

    None with under two weeks of history: there is no previous week yet.
    """
    spans = weeks(bars)
    if len(spans) < 2:
        return None
    monday, first, last = spans[-2]
    window = bars[first:last + 1]
    return {"week_of": monday.isoformat(),
            "high": round(max(b.high for b in window), 2),
            "low": round(min(b.low for b in window), 2),
            "sessions": len(window)}


@dataclass
class Event:
    """One trip under a previous week's low."""
    week_start_idx: int       # first session of the week whose low was broken
    week_end_idx: int
    level: float              # that week's low
    undercut_idx: int         # first session to trade beneath it
    low_idx: int              # the session that went furthest
    low: float                # how far
    reclaim_idx: int | None   # first close back above the level, if any yet

    @property
    def undercut_pct(self) -> float:
        return 100.0 * (self.level - self.low) / self.level if self.level else 0.0


def events(bars: Sequence[Bar], max_undercut_pct: float = 4.0,
           max_reclaim_sessions: int = 2) -> list[Event]:
    """Every sweep of a previous week's low in the history, oldest first.

    One a week at most: the first session of a week to trade under the week
    before's low opens the event, and the first close back above that level
    within `max_reclaim_sessions` sessions closes it. The reclaim may fall in
    the following week; the level is the one that was broken and does not
    move. A trip that goes more than `max_undercut_pct` beneath the level is
    a breakdown and not a sweep, and is no event at all. An event with no
    reclaim is kept only while there is still time for one, which is to say
    only when it is the live edge of the chart.
    """
    out: list[Event] = []
    spans = weeks(bars)
    count = len(bars)
    for position in range(1, len(spans)):
        _, prev_first, prev_last = spans[position - 1]
        _, first, last = spans[position]
        level = min(b.low for b in bars[prev_first:prev_last + 1])
        if level <= 0:
            continue
        undercut = next((i for i in range(first, last + 1) if bars[i].low < level), None)
        if undercut is None:
            continue
        limit = min(count - 1, undercut + max_reclaim_sessions)
        reclaim = next((i for i in range(undercut, limit + 1)
                        if bars[i].close > level), None)
        end = reclaim if reclaim is not None else limit
        low_idx = min(range(undercut, end + 1), key=lambda i: bars[i].low)
        event = Event(prev_first, prev_last, level, undercut, low_idx,
                      bars[low_idx].low, reclaim)
        if event.undercut_pct > max_undercut_pct:
            continue
        if reclaim is None and undercut + max_reclaim_sessions < count - 1:
            # Its window closed without a close back above. Over.
            continue
        out.append(event)
    return out


def healthy(event: Event, closes: Sequence[float], sma50: Sequence[float | None],
            sma200: Sequence[float | None], above_50: bool = True,
            stacked: bool = True) -> bool:
    """Whether the stock was in good order the session before it was swept.

    Judged the session before, not on the day: the day itself is a stock
    under a level, which says nothing about the trend it came from. A stock
    with no 200-day average yet is not judged on one.
    """
    before = event.undercut_idx - 1
    if before < 0:
        return False
    line = sma50[before]
    if above_50 and not (line and closes[before] > line):
        return False
    slow = sma200[before]
    if stacked and line and slow and line <= slow:
        return False
    return True


def near_high(bars: Sequence[Bar], idx: int, limit_pct: float | None) -> bool:
    """Whether the close at `idx` sat within `limit_pct` of the highest high of
    the year up to it. None for the limit is no test."""
    if limit_pct is None:
        return True
    window = bars[max(0, idx - 252):idx + 1]
    high = max((b.high for b in window), default=0.0)
    return bool(high) and 100.0 * (high - bars[idx].close) / high <= float(limit_pct)


def close_position(bar: Bar) -> float:
    """Where in its own range a session closed: 0 at the low, 100 at the high.
    A session with no range closed at both, and is given the middle."""
    span = bar.high - bar.low
    return 50.0 if span <= 0 else 100.0 * (bar.close - bar.low) / span


def screened(bars: Sequence[Bar], closes: Sequence[float],
             sma50: Sequence[float | None], sma200: Sequence[float | None], *,
             max_undercut_pct: float = 4.0, max_reclaim_sessions: int = 2,
             above_50: bool = True, stacked: bool = True,
             max_from_high_pct: float | None = None,
             min_close_position: float = 0.0) -> list[Event]:
    """The events that pass every test bars alone can make, oldest first.

    This is the one definition of "the screen would have shown this", used by
    the nightly scan and by the record of what happened afterwards, so the
    two cannot come to disagree about the screen's own history. Relative
    strength is the caller's test: it needs the whole market, not one chart.
    """
    out: list[Event] = []
    for event in events(bars, max_undercut_pct, max_reclaim_sessions):
        if not healthy(event, closes, sma50, sma200, above_50=above_50, stacked=stacked):
            continue
        if not near_high(bars, event.undercut_idx - 1, max_from_high_pct):
            continue
        if (event.reclaim_idx is not None and min_close_position > 0
                and close_position(bars[event.reclaim_idx]) < min_close_position):
            # Back above the level, but sold into the close: not a rejection
            # of lower prices so much as a pause on the way to them.
            continue
        out.append(event)
    return out


def gates(params) -> dict:
    """The screen's dials as `screened` takes them. `params` is a
    patterns.params.Params; anything it does not carry is left at no test."""
    limit = params.get("max_from_52w_high_pct")
    return {
        "max_undercut_pct": float(params.get("max_undercut_pct", 4.0)),
        "max_reclaim_sessions": int(params.get("max_reclaim_sessions", 2)),
        "above_50": bool(params.get("require_above_50ma", True)),
        "stacked": bool(params.get("require_50_above_200", True)),
        "max_from_high_pct": None if limit is None else float(limit),
        "min_close_position": float(params.get("min_close_position_pct", 0.0) or 0.0),
    }


def lost_level(event: Event, bars: Sequence[Bar]) -> int | None:
    """The first session after the reclaim to close back under the level, if
    any. A reclaim that does this has failed by its own definition, whatever
    the 50-day line says."""
    if event.reclaim_idx is None:
        return None
    return next((i for i in range(event.reclaim_idx + 1, len(bars))
                 if bars[i].close < event.level), None)


def details(event: Event, bars: Sequence[Bar]) -> dict:
    """The event in the shape a card prints it."""
    reclaimed = event.reclaim_idx is not None
    return {
        "week_of": week_of(bars[event.week_start_idx].date).isoformat(),
        "level": round(event.level, 2),
        "undercut_date": bars[event.undercut_idx].date.isoformat(),
        "low": round(event.low, 2),
        "low_date": bars[event.low_idx].date.isoformat(),
        "undercut_pct": round(event.undercut_pct, 2),
        "reclaim_date": bars[event.reclaim_idx].date.isoformat() if reclaimed else None,
        # Zero is the strongest form: under it and back above it in one session.
        "sessions_to_reclaim": (event.reclaim_idx - event.undercut_idx
                                if reclaimed else None),
        # Where in its own range the reclaim session closed, 0 to 100.
        "close_position": (round(close_position(bars[event.reclaim_idx]))
                           if reclaimed else None),
    }
