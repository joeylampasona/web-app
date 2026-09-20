"""What actually happened to the breakouts this site showed.

The screens say what is setting up. Nothing said whether it worked. This does,
on real prices, without a portfolio in the way: every breakout that passed a
screen's gates on its own day, and what the stock did afterwards.

It reuses `backtest.engine.candidates` rather than re-deriving which breakouts
count. That function is the one definition of "this screen would have shown
this, on this day", and a second copy of that judgement would be free to
disagree with the backtest about its own history.

The same survivorship caveat applies here as to every backtest figure, and for
the same reason: a provider's free tier carries no delisted companies, so the
names that failed hardest are the ones missing. These numbers are flattered,
they are labelled as flattered, and they are still the most honest thing the
site can say about whether any of this works.
"""
from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import asdict, dataclass

from backtest import engine
from data.market import Market
from patterns.params import BASE_SCREEN_KEYS, SCREENS, Params

# Six months. Long enough that a base has had time to resolve, short enough that
# it describes the market someone is looking at rather than the one before it.
DEFAULT_WINDOW_DAYS = 180

# A breakout needs room to have done something. Anything younger is reported
# separately as still open rather than counted as a result.
SETTLED_SESSIONS = 10

# A breakout that closes back under its pivot in the first fortnight failed; one
# that dips under it four months later has simply had a bad week in an ongoing
# move. Measuring "ever closed below the pivot" conflates the two and reports
# almost everything as a failure, which is worse than not reporting it.
FAILURE_SESSIONS = 10


@dataclass
class Outcome:
    symbol: str
    name: str
    breakout_date: str
    sessions_since: int
    breakout_close: float
    pivot: float
    last_close: float
    now_pct: float
    peak_pct: float
    worst_pct: float
    failed_fast: bool
    now_below_pivot: bool
    rs_at_breakout: int | None


def compute(market: Market, timeline, window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """Per screen: every breakout inside the window, and how it has gone."""
    as_of = market.as_of
    out: dict[str, dict] = {}
    # Base screens only. This reuses engine.candidates to re-derive breakouts
    # historically, and the engine can only rebuild a base — see
    # BASE_SCREEN_KEYS. A shape screen's history is not reconstructable here.
    for key in BASE_SCREEN_KEYS:
        spec = SCREENS[key]
        params = Params(key)
        rows: list[Outcome] = []
        for symbol, found in engine.candidates(market, params, timeline).items():
            bars = market.series.get(symbol) or []
            for cand in found:
                if as_of and (as_of - cand.date).days > window_days:
                    continue
                after = bars[cand.idx + 1:]
                if not after:
                    continue
                entry = cand.breakout_close
                if entry <= 0:
                    continue
                ref = market.refs.get(symbol)
                rows.append(Outcome(
                    symbol=symbol,
                    name=(ref.name if ref else symbol),
                    breakout_date=cand.date.isoformat(),
                    sessions_since=len(after),
                    breakout_close=round(entry, 2),
                    pivot=round(cand.pivot, 2),
                    last_close=round(after[-1].close, 2),
                    now_pct=round(100.0 * (after[-1].close - entry) / entry, 2),
                    peak_pct=round(100.0 * (max(b.high for b in after) - entry) / entry, 2),
                    worst_pct=round(100.0 * (min(b.low for b in after) - entry) / entry, 2),
                    # Cleared the lid, then closed back under it almost at once.
                    failed_fast=any(b.close < cand.pivot
                                    for b in after[:FAILURE_SESSIONS]),
                    now_below_pivot=after[-1].close < cand.pivot,
                    rs_at_breakout=cand.rs_rating,
                ))
        rows.sort(key=lambda r: r.breakout_date, reverse=True)
        out[key] = {"screen": key, "name": spec.name,
                    "window_days": window_days,
                    **_summarise(rows),
                    "breakouts": [asdict(r) for r in rows]}
    return {"as_of": as_of.isoformat() if as_of else None,
            "window_days": window_days,
            "screens": out}


def _summarise(rows: list[Outcome]) -> dict:
    settled = [r for r in rows if r.sessions_since >= SETTLED_SESSIONS]
    if not settled:
        return {"total": len(rows), "settled": 0, "too_soon": len(rows),
                "up": 0, "down": 0, "failed_fast": 0, "below_pivot": 0,
                "median_now_pct": None, "median_peak_pct": None,
                "share_up_pct": None, "share_failed_pct": None}
    returns = [r.now_pct for r in settled]
    up = sum(1 for r in settled if r.now_pct > 0)
    failed = sum(1 for r in settled if r.failed_fast)
    below = sum(1 for r in settled if r.now_below_pivot)
    return {
        "total": len(rows),
        "settled": len(settled),
        "too_soon": len(rows) - len(settled),
        "up": up,
        "down": len(settled) - up,
        "failed_fast": failed,
        "below_pivot": below,
        "median_now_pct": round(statistics.median(returns), 2),
        "median_peak_pct": round(statistics.median([r.peak_pct for r in settled]), 2),
        "share_up_pct": round(100.0 * up / len(settled), 1),
        "share_failed_pct": round(100.0 * failed / len(settled), 1),
    }
