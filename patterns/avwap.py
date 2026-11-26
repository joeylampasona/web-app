"""The average price paid since a day that mattered.

A volume-weighted average price anchored to an event answers one question a
moving average cannot: of everyone who has bought since the report, or since
the breakout, is the average buyer up or down? Above the line they are in
profit and tend to defend it. Below it they are underwater and tend to sell
into strength.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------

A true VWAP is computed from every trade. This is computed from daily bars:
each session contributes its typical price, the mean of its high, low and
close, weighted by its volume. Over weeks the two agree closely, because a
session's typical price is a fair stand-in for where its volume traded. On
the anchor day itself, and for an anchor only a few sessions old, they can
differ by a noticeable amount, so the page says "from daily bars" wherever
the figure is shown.

THE ANCHORS
-----------

  earnings   the session that carried the last report. The source gives the
             day of a report and not the hour, so a report after the close
             lands on the next session and one before the open on the same
             session. Of the report day's session and the one after it, the
             one with the heavier volume is taken: the news day is the one
             the volume came on.
  breakout   the session a live setup cleared its level.
  year       the first session of the calendar year.

The browser already holds the last hundred and eighty bars and draws its own
moving averages from them. It draws these lines the same way, so the line is
not published. What is published is the running totals up to the first bar
the browser has, for an anchor older than that, and nothing but the date for
one that is not.
"""
from __future__ import annotations

import datetime as dt
from typing import Sequence

from data.types import Bar

#: What each anchor is called on the page.
LABELS = {"earnings": "Since the last report", "breakout": "Since the breakout",
          "year": "Since the year began"}


def typical(bar: Bar) -> float:
    return (bar.high + bar.low + bar.close) / 3.0


def totals(bars: Sequence[Bar], start: int, end: int) -> tuple[float, float]:
    """(sum of typical price x volume, sum of volume) over bars[start:end]."""
    money = volume = 0.0
    for bar in bars[max(0, start):max(0, end)]:
        if bar.volume and bar.volume > 0:
            money += typical(bar) * bar.volume
            volume += bar.volume
    return money, volume


def value(bars: Sequence[Bar], start: int, end: int | None = None) -> float | None:
    """The anchored VWAP from bars[start] through bars[end - 1]. None when
    nothing traded in between."""
    money, volume = totals(bars, start, len(bars) if end is None else end)
    return money / volume if volume > 0 else None


def index_on_or_after(bars: Sequence[Bar], day: dt.date) -> int | None:
    for index, bar in enumerate(bars):
        if bar.date >= day:
            return index
    return None


def earnings_session(bars: Sequence[Bar], report: dt.date) -> int | None:
    """The index of the session that carried a report dated `report`.

    The report day's own session if it was one, else the first after it; and
    when the session after that traded more, that one instead. See THE
    ANCHORS above for why volume decides.
    """
    first = index_on_or_after(bars, report)
    if first is None:
        return None
    if bars[first].date != report:
        return first                    # a weekend or holiday: the next session has it
    after = first + 1
    if after < len(bars) and bars[after].volume > bars[first].volume:
        return after
    return first


def year_session(bars: Sequence[Bar]) -> int | None:
    """The first session of the last bar's calendar year, if the history
    reaches back to the year before it; otherwise it cannot be told from a
    stock that simply listed later."""
    if not bars:
        return None
    year = bars[-1].date.year
    index = next((i for i, bar in enumerate(bars) if bar.date.year == year), None)
    if index is None or index == 0:
        return None
    return index


def summary(bars: Sequence[Bar], anchors: Sequence[tuple[str, int | None]],
            shipped: int) -> list[dict]:
    """One row an anchor, for the stock's page.

    `anchors` is (kind, index into bars) pairs; an index of None is an anchor
    this stock does not have. `shipped` is how many bars the page is sent, so
    the seed can cover whatever lies before them.
    """
    out: list[dict] = []
    count = len(bars)
    if count < 2:
        return out
    first_shipped = max(0, count - shipped)
    last = bars[-1]
    for kind, start in anchors:
        if start is None or start < 0 or start >= count:
            continue
        now = value(bars, start)
        if now is None or now <= 0:
            continue
        # Where the close sat against the line a session ago, to say whether
        # tonight is the night it crossed.
        before = value(bars, start, count - 1) if start < count - 1 else None
        crossed = None
        if before:
            was_above = bars[-2].close > before
            is_above = last.close > now
            if was_above != is_above:
                crossed = "up" if is_above else "down"
        seed_money, seed_volume = (totals(bars, start, first_shipped)
                                   if start < first_shipped else (0.0, 0.0))
        out.append({
            "anchor": kind,
            "label": LABELS.get(kind, kind),
            "from": bars[start].date.isoformat(),
            "sessions": count - start,
            "value": round(now, 2),
            "above": last.close > now,
            "vs_pct": round(100.0 * (last.close / now - 1.0), 2),
            # "up" or "down" on the session the close changed sides, else null.
            "crossed": crossed,
            # Running totals before the first bar the page is sent. Both zero
            # when the anchor is inside what the page has.
            "seed_money": round(seed_money, 2),
            "seed_volume": round(seed_volume, 2),
        })
    return out
