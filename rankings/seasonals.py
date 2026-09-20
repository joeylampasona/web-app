"""Month-by-month returns, one row per calendar year.

A grid rather than an average, and that choice is the honest part.

An average monthly return hides how many months went into it. "September: -1.8%"
reads identically whether it came from eighty Septembers or from three, and a
reader has no way to tell which they are looking at. A grid cannot hide it: the
rows ARE the years, so a page built from four of them looks like a page built
from four of them.

That matters here more than it would elsewhere. This site holds about three and
a half years of history, because the data tier it runs on serves roughly that
much. Four rows, two of them partial. Real seasonal work uses decades. The grid
is still worth showing — it is a true record of what each month did — but it is
a record, not a base rate, and the page says so in those words.

The summary row carries percentages: the average of the months observed, and
how often they rose. Both are published WITH the number of observations behind
them, always, because an average of three Septembers and an average of eighty
are different objects and the figure alone cannot tell them apart. The count is
not a footnote here; it sits in the cell.
"""
from __future__ import annotations

import calendar
import datetime as dt
import logging
from dataclasses import dataclass, field

from data.types import Bar

log = logging.getLogger(__name__)

MONTHS = list(range(1, 13))
MONTH_LABELS = [calendar.month_abbr[m] for m in MONTHS]

#: Below this many sessions a month is treated as not having happened rather
#: than as a return. A month with three sessions in it is a data boundary, not
#: a short month, and averaging it in would be reporting an artefact.
MIN_SESSIONS_IN_MONTH = 5


@dataclass
class MonthCell:
    year: int
    month: int
    return_pct: float | None
    sessions: int

    def to_json(self) -> dict:
        return {
            "month": self.month,
            "return_pct": (round(self.return_pct, 2)
                           if self.return_pct is not None else None),
            "sessions": self.sessions,
        }


@dataclass
class YearRow:
    year: int
    months: list[MonthCell]
    year_pct: float | None
    partial: bool

    def to_json(self) -> dict:
        return {
            "year": self.year,
            "months": [c.to_json() for c in self.months],
            "year_pct": round(self.year_pct, 2) if self.year_pct is not None else None,
            # A year the history starts or ends inside is not a year's return,
            # and a column of them beside complete years would invite exactly
            # that comparison.
            "partial": self.partial,
        }


@dataclass
class Seasonals:
    symbol: str
    name: str
    years: list[YearRow] = field(default_factory=list)
    #: Per month: the average observed return, how often it rose, and the
    #: number of observations that produced both.
    tally: dict[int, dict] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "months": MONTH_LABELS,
            "years": [y.to_json() for y in self.years],
            "tally": {str(m): self.tally.get(
                m, {"up": 0, "down": 0, "avg_pct": None, "up_rate": None,
                    "observations": 0})
                for m in MONTHS},
            "observed_years": len(self.years),
        }


def _monthly(bars: list[Bar]) -> dict[tuple[int, int], list[Bar]]:
    out: dict[tuple[int, int], list[Bar]] = {}
    for bar in bars:
        out.setdefault((bar.date.year, bar.date.month), []).append(bar)
    return out


def build(symbol: str, name: str, bars: list[Bar]) -> Seasonals | None:
    """The grid for one symbol. None when there is not a single usable month."""
    if not bars:
        return None
    buckets = _monthly(bars)
    if not buckets:
        return None

    first, last = bars[0].date, bars[-1].date
    years = sorted({d.year for d, _ in ((b.date, None) for b in bars)})

    rows: list[YearRow] = []
    tally: dict[int, dict] = {m: {"up": 0, "down": 0} for m in MONTHS}
    observed_by_month: dict[int, list[float]] = {m: [] for m in MONTHS}

    for year in years:
        cells: list[MonthCell] = []
        for month in MONTHS:
            chunk = buckets.get((year, month)) or []
            if len(chunk) < MIN_SESSIONS_IN_MONTH:
                cells.append(MonthCell(year, month, None, len(chunk)))
                continue
            # Measured close to close across the month, using the last close of
            # the previous month as the base where we have it — that is the
            # return an owner actually experienced, rather than first-close to
            # last-close which silently drops the gap into the month.
            opening = _previous_close(buckets, year, month) or chunk[0].close
            closing = chunk[-1].close
            pct = (100.0 * (closing / opening - 1.0)) if opening else None
            cells.append(MonthCell(year, month, pct, len(chunk)))
            if pct is not None:
                tally[month]["up" if pct >= 0 else "down"] += 1
                observed_by_month[month].append(pct)

        observed = [c for c in cells if c.return_pct is not None]
        # The year's own return, compounded from its months rather than summed:
        # adding percentages is wrong and the error grows with the year.
        year_pct: float | None = None
        if observed:
            factor = 1.0
            for cell in observed:
                factor *= (1.0 + (cell.return_pct or 0.0) / 100.0)
            year_pct = 100.0 * (factor - 1.0)

        partial = (year == first.year and first.month > 1) or \
                  (year == last.year and last.month < 12)
        rows.append(YearRow(year, cells, year_pct, partial))

    for month in MONTHS:
        seen = observed_by_month[month]
        entry = tally[month]
        entry["observations"] = len(seen)
        # A mean, stated only alongside the n that produced it. With three or
        # four observations this is a description of those three or four
        # months, and the page is built so it can never be read as more.
        entry["avg_pct"] = round(sum(seen) / len(seen), 2) if seen else None
        total = entry["up"] + entry["down"]
        entry["up_rate"] = round(100.0 * entry["up"] / total, 0) if total else None

    rows.sort(key=lambda r: -r.year)
    return Seasonals(symbol=symbol, name=name, years=rows, tally=tally)


def _previous_close(buckets: dict[tuple[int, int], list[Bar]],
                    year: int, month: int) -> float | None:
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    chunk = buckets.get((prev_year, prev_month))
    return chunk[-1].close if chunk else None
