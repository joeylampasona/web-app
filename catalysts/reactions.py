"""How a stock has moved on its earnings reports.

The question a breakout trader has before an earnings date is not whether the
company will beat, it is how far the stock tends to go either way -- because
that is the size of the gap a stop placed under a base has to survive.

Measured close to close across the report: from the last session before the
report day to the first session after it. That window contains the reaction
whether the company reported before the open or after the close, and the
source does not reliably say which. The cost is one ordinary session of drift
in every reading, which is small next to an earnings move and is the same for
every company, so comparisons between them still hold.
"""
from __future__ import annotations

import bisect
import datetime as dt
from typing import Sequence

# Recent reports only. Four is a year of quarters; eight is two, and a
# company's earnings behaviour two years ago is a different company's.
LIMIT = 8

# A window wider than this means bars are missing around the report, and the
# "move" would include days that are not the reaction.
MAX_WINDOW_DAYS = 6


def moves(bars: Sequence, report_dates: Sequence[dt.date], as_of: dt.date,
          limit: int = LIMIT) -> list[dict]:
    """[{date, move_pct}] newest first, one per measurable report."""
    if not bars:
        return []
    days = [b.date for b in bars]
    out: list[dict] = []
    for day in sorted(set(report_dates), reverse=True):
        if day >= as_of:
            continue
        i = bisect.bisect_left(days, day)
        if i == 0 or i >= len(bars):
            continue
        before = i - 1
        # Reported on a session: the reaction is the next session's close. On a
        # weekend or holiday: the first session after it already contains it.
        after = i + 1 if days[i] == day else i
        if after >= len(bars):
            continue
        if (days[after] - days[before]).days > MAX_WINDOW_DAYS:
            continue
        prior = bars[before].close
        if not prior:
            continue
        out.append({"date": day.isoformat(),
                    "move_pct": round((bars[after].close / prior - 1) * 100, 2)})
        if len(out) >= limit:
            break
    return out


def summary(reports: list[dict]) -> dict | None:
    """Average size, largest, and how many went up. None with no reports."""
    if not reports:
        return None
    sizes = [abs(r["move_pct"]) for r in reports]
    largest = max(reports, key=lambda r: abs(r["move_pct"]))
    return {
        "count": len(reports),
        "avg_abs_pct": round(sum(sizes) / len(sizes), 2),
        "largest": largest,
        "up": sum(1 for r in reports if r["move_pct"] > 0),
        "reports": reports,
    }
