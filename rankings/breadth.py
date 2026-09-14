"""Market breadth, each metric with prior day, week ago and a 20-day series.

The breakout and failed-poke counts here are deliberately market-wide and
screen-independent: a close above the highest high of the prior 50 sessions,
and an intraday push above that level that closed back under it. Screen-level
breakouts come from the scan and are counted separately.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from data import settings
from data.market import Market
from patterns import indicators

WEEK = 5
BREAKOUT_LOOKBACK = 50
YEAR = 252


@dataclass
class Card:
    key: str
    label: str
    unit: str                      # percent | count
    value: float
    counts: dict[str, float] = field(default_factory=dict)
    prior_day: float | None = None
    week_ago: float | None = None
    wow_delta: float | None = None
    series: list[dict] = field(default_factory=list)
    note: str = ""

    def to_json(self) -> dict:
        return {
            "key": self.key, "label": self.label, "unit": self.unit,
            "value": round(self.value, 2), "counts": self.counts,
            "prior_day": None if self.prior_day is None else round(self.prior_day, 2),
            "week_ago": None if self.week_ago is None else round(self.week_ago, 2),
            "wow_delta": None if self.wow_delta is None else round(self.wow_delta, 2),
            "series": self.series, "note": self.note,
        }


class _Panel:
    """Per-symbol arrays aligned to each symbol's own bars, plus a date index."""

    def __init__(self, market: Market) -> None:
        self.market = market
        self.idx: dict[str, dict[dt.date, int]] = {}
        self.sma50: dict[str, list] = {}
        self.sma200: dict[str, list] = {}
        self.hi252: dict[str, list] = {}
        self.lo252: dict[str, list] = {}
        self.hi50: dict[str, list] = {}
        # The short end of the stack. The 50 and 200 are already here; these are
        # the two that measure a timeframe nothing else on this site covers.
        self.sma9: dict[str, list] = {}
        self.sma21: dict[str, list] = {}
        for sym in market.universe:
            bars = market.series.get(sym) or []
            if not bars:
                continue
            cl = [b.close for b in bars]
            self.idx[sym] = {b.date: i for i, b in enumerate(bars)}
            self.sma9[sym] = indicators.sma(cl, 9)
            self.sma21[sym] = indicators.sma(cl, 21)
            self.sma50[sym] = indicators.sma(cl, 50)
            self.sma200[sym] = indicators.sma(cl, 200)
            self.hi252[sym] = indicators.rolling_max([b.high for b in bars], YEAR)
            self.lo252[sym] = indicators.rolling_min([b.low for b in bars], YEAR)
            self.hi50[sym] = indicators.rolling_max([b.high for b in bars], BREAKOUT_LOOKBACK)


def _snapshot(panel: _Panel, day: dt.date) -> dict[str, float]:
    cfg = settings.get("rankings", {}) or {}
    near_high = float(cfg.get("near_high_pct", 5.0)) / 100.0
    near_low = float(cfg.get("near_low_pct", 5.0)) / 100.0
    m = panel.market
    counts = dict(universe=0, near_high=0, near_low=0, uptrend=0, up=0, down=0,
                  above_50=0, above_200=0, breakout=0, failed_poke=0,
                  stacked=0, stack_known=0)
    for sym, index in panel.idx.items():
        i = index.get(day)
        if i is None or i < 1:
            continue
        bars = m.series[sym]
        bar = bars[i]
        counts["universe"] += 1
        prev = bars[i - 1].close
        if bar.close > prev:
            counts["up"] += 1
        elif bar.close < prev:
            counts["down"] += 1

        hi = panel.hi252[sym][i]
        lo = panel.lo252[sym][i]
        if hi and bar.close >= hi * (1.0 - near_high):
            counts["near_high"] += 1
        if lo and bar.close <= lo * (1.0 + near_low):
            counts["near_low"] += 1

        s50 = panel.sma50[sym][i]
        s200 = panel.sma200[sym][i]
        if s50 and bar.close > s50:
            counts["above_50"] += 1
        if s200 and bar.close > s200:
            counts["above_200"] += 1
        if s50 and s200 and bar.close > s50 and bar.close > s200 and s50 > s200:
            counts["uptrend"] += 1

        # A full stack: 9 above 21 above 50 above 200. Counted against the names
        # that have enough history to have all four, not against the universe —
        # a young listing has no 200-day average, and folding it in as "not
        # stacked" would quietly understate the reading.
        s9 = panel.sma9[sym][i]
        s21 = panel.sma21[sym][i]
        if None not in (s9, s21, s50, s200):
            counts["stack_known"] += 1
            if s9 > s21 > s50 > s200:
                counts["stacked"] += 1

        if i >= BREAKOUT_LOOKBACK:
            lid = panel.hi50[sym][i - 1]
            if lid:
                if bar.close > lid:
                    counts["breakout"] += 1
                elif bar.high > lid:
                    counts["failed_poke"] += 1
    return counts


def compute(market: Market) -> dict:
    days = int(settings.get("rankings.breadth_series_days", 20))
    panel = _Panel(market)
    calendar = [d for d in market.calendar if d <= market.as_of][-(days + WEEK + 2):]
    snaps = {d: _snapshot(panel, d) for d in calendar}
    sessions = [d for d in calendar if snaps[d]["universe"] > 0]
    if not sessions:
        return {"as_of": market.as_of.isoformat(), "universe_size": 0, "cards": []}

    def pct(day: dt.date, key: str) -> float:
        s = snaps[day]
        return 100.0 * s[key] / s["universe"] if s["universe"] else 0.0

    def at(back: int) -> dt.date | None:
        return sessions[-1 - back] if len(sessions) > back else None

    today, prior, week = at(0), at(1), at(WEEK)
    tail = sessions[-days:]

    def make(key: str, label: str, count_key: str, unit: str, counts: dict,
             note: str = "") -> Card:
        if unit == "percent":
            value = pct(today, count_key)
            p = pct(prior, count_key) if prior else None
            w = pct(week, count_key) if week else None
            series = [{"date": d.isoformat(), "value": round(pct(d, count_key), 2)} for d in tail]
        else:
            value = float(snaps[today][count_key])
            p = float(snaps[prior][count_key]) if prior else None
            w = float(snaps[week][count_key]) if week else None
            series = [{"date": d.isoformat(), "value": snaps[d][count_key]} for d in tail]
        return Card(key=key, label=label, unit=unit, value=value, counts=counts,
                    prior_day=p, week_ago=w,
                    wow_delta=None if w is None else value - w,
                    series=series, note=note)

    s = snaps[today]
    universe_size = s["universe"]
    five = sessions[-5:]

    cards = [
        make("near_52w_highs", "Near 52-week highs", "near_high", "percent",
             {"count": s["near_high"], "universe": universe_size,
              "near_lows": s["near_low"]},
             "Within 5% of the highest price of the last year."),
        make("near_52w_lows", "Near 52-week lows", "near_low", "percent",
             {"count": s["near_low"], "universe": universe_size,
              "near_highs": s["near_high"]},
             "Within 5% of the lowest price of the last year."),
        make("confirmed_uptrend", "In a confirmed uptrend", "uptrend", "percent",
             {"count": s["uptrend"], "universe": universe_size},
             "Above both the 50-day and 200-day lines, with the 50 above the 200."),
        make("up_today", "Up today", "up", "percent",
             {"up": s["up"], "down": s["down"], "universe": universe_size},
             "Closed higher than the session before."),
        make("above_50ma", "Above the 50-day line", "above_50", "percent",
             {"count": s["above_50"], "universe": universe_size}),
        make("above_200ma", "Above the 200-day line", "above_200", "percent",
             {"count": s["above_200"], "universe": universe_size}),
        make("full_stack", "Averages fully stacked", "stacked", "percent",
             {"count": s["stacked"], "universe": s["stack_known"] or universe_size},
             "The 9, 21, 50 and 200-day averages in order, fastest above slowest. "
             "Measured against the names with enough history to have all four."),
        make("breakouts", "Broke out today", "breakout", "count",
             {"today": s["breakout"],
              "yesterday": snaps[prior]["breakout"] if prior else 0,
              "five_session_total": sum(snaps[d]["breakout"] for d in five)},
             "A close above the highest high of the prior 50 sessions."),
        make("failed_pokes", "Tested the pivot and failed", "failed_poke", "count",
             {"today": s["failed_poke"],
              "yesterday": snaps[prior]["failed_poke"] if prior else 0,
              "five_session_total": sum(snaps[d]["failed_poke"] for d in five)},
             "Pushed above that level intraday and closed back under it."),
    ]

    return {
        "as_of": market.as_of.isoformat(),
        "universe_size": universe_size,
        "cards": [c.to_json() for c in cards],
    }
