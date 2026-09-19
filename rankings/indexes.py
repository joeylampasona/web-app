"""Broad-market index rows, and the regime check the whole site leans on.

Two jobs, kept in one place because they read the same bars:

1. A row per configured index for the home page's strip — last close, the day's
   change, and where price sits against its 200-day line.
2. `regime()`, which answers "is the benchmark above its 200-day average?".
   `config/settings.yaml` has named that rule as `backtest.strong_market_rule`
   since the project began and nothing ever computed it. It is the most-used
   regime filter in this style of trading: breakouts bought beneath it fail far
   more often, and the site was silent about it.

Nothing here invents a number when the data is thin. An index with no bars is
omitted rather than rendered as a dash, and an index with under 200 sessions
reports `above_200 = None` rather than guessing. A regime filter that quietly
defaults to "fine" is worse than no regime filter, because it is trusted.
"""
from __future__ import annotations

from typing import Any

from data import settings
from data.market import Market
from patterns import indicators

# A 200-session average needs 200 sessions. Below that there is no answer, and
# saying so is the point.
MIN_HISTORY = 200


def _row(market: Market, symbol: str) -> dict[str, Any] | None:
    bars = market.series.get(symbol) or []
    if not bars:
        return None

    closes = [b.close for b in bars]
    last = closes[-1]
    prior = closes[-2] if len(closes) >= 2 else None
    change_pct = None if prior in (None, 0) else (last - prior) / prior * 100.0

    above_200: bool | None = None
    vs_200_pct: float | None = None
    if len(closes) >= MIN_HISTORY:
        ma = indicators.sma(closes, 200)[-1]
        if ma:
            above_200 = last >= ma
            vs_200_pct = (last - ma) / ma * 100.0

    ref = market.refs.get(symbol)
    return {
        "symbol": symbol,
        "name": getattr(ref, "name", None) or symbol,
        "close": round(last, 2),
        "change_pct": None if change_pct is None else round(change_pct, 2),
        "above_200": above_200,
        "vs_200_pct": None if vs_200_pct is None else round(vs_200_pct, 2),
        "sessions": len(closes),
    }


def rows(market: Market) -> list[dict[str, Any]]:
    """One row per configured index that actually has bars, in config order."""
    wanted = list(settings.get("rankings.indexes", []) or [])
    out = []
    for symbol in wanted:
        row = _row(market, symbol)
        if row is not None:
            out.append(row)
    return out


def regime(market: Market) -> dict[str, Any]:
    """Is the benchmark above its 200-day line?

    `above` is None when it cannot be known, and callers must treat that as
    "no answer" rather than as False. The three states are deliberate: above,
    below, and not enough history to say.
    """
    row = _row(market, market.benchmark)
    if row is None:
        return {"symbol": market.benchmark, "above": None,
                "vs_200_pct": None, "sessions": 0,
                "note": f"No bars for {market.benchmark}, so the regime is unknown."}

    if row["above_200"] is None:
        return {"symbol": market.benchmark, "above": None,
                "vs_200_pct": None, "sessions": row["sessions"],
                "note": (f"{market.benchmark} has {row['sessions']} sessions of history, "
                         f"under the {MIN_HISTORY} a 200-day average needs.")}

    side = "above" if row["above_200"] else "below"
    return {
        "symbol": market.benchmark,
        "above": row["above_200"],
        "vs_200_pct": row["vs_200_pct"],
        "sessions": row["sessions"],
        "note": f"{market.benchmark} is {abs(row['vs_200_pct']):.1f}% {side} its 200-day average.",
    }
