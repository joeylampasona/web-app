"""yfinance-backed earnings dates and option chains.

yfinance scrapes an undocumented endpoint. It breaks without notice and rate
limits opaquely, so every call here degrades to empty rather than raising: a
missing earnings date costs a badge, a failed nightly run costs the whole site.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence

from data.types import EarningsEvent, OptionChain, OptionExpiry

log = logging.getLogger(__name__)


def _yf():
    try:
        import yfinance  # noqa: PLC0415 - optional dependency, imported lazily
        return yfinance
    except Exception as exc:                      # noqa: BLE001
        log.warning("yfinance unavailable (%s) — earnings and IV will be empty", exc)
        return None


def earnings_dates(symbols: Sequence[str]) -> dict[str, list[EarningsEvent]]:
    yf = _yf()
    out: dict[str, list[EarningsEvent]] = {}
    if yf is None:
        return out
    for symbol in symbols:
        try:
            frame = yf.Ticker(symbol).get_earnings_dates(limit=8)
            if frame is None or frame.empty:
                continue
            events: list[EarningsEvent] = []
            for stamp, row in frame.iterrows():
                date = stamp.date() if hasattr(stamp, "date") else stamp
                reported = row.get("Reported EPS")
                confirmed = "confirmed" if reported == reported and reported is not None \
                    else "tentative"
                events.append(EarningsEvent(symbol, date, confirmed))
            if events:
                out[symbol] = events
        except Exception as exc:                  # noqa: BLE001
            log.debug("earnings lookup failed for %s: %s", symbol, exc)
    return out


def option_chain(symbol: str) -> OptionChain | None:
    yf = _yf()
    if yf is None:
        return None
    try:
        ticker = yf.Ticker(symbol)
        expiries = list(ticker.options or [])
        if not expiries:
            return None
        spot = float(ticker.fast_info.get("last_price") or 0.0)
        rows: list[OptionExpiry] = []
        for text in expiries[:8]:
            chain = ticker.option_chain(text)
            frames = [f for f in (chain.calls, chain.puts) if f is not None and not f.empty]
            if not frames:
                continue
            ivs: list[float] = []
            for frame in frames:
                near = frame.copy()
                if spot and "strike" in near:
                    near["distance"] = (near["strike"] - spot).abs()
                    near = near.nsmallest(6, "distance")
                ivs.extend(float(v) for v in near.get("impliedVolatility", [])
                           if v == v and v > 0)
            if ivs:
                rows.append(OptionExpiry(dt.date.fromisoformat(text),
                                         sum(ivs) / len(ivs), len(ivs)))
        return OptionChain(symbol=symbol, spot=spot, expiries=rows) if rows else None
    except Exception as exc:                      # noqa: BLE001
        log.debug("option chain failed for %s: %s", symbol, exc)
        return None
