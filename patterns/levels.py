"""Three-touch support and resistance: prices the market has tested repeatedly.

Ported from Market Desk's scanners/levels.py, which draws the same levels on
its pick cards; here they are computed for every stock in the universe.

A level is a cluster of pivot highs and lows -- a session whose high or low is
the extreme of the five around it -- over the last LOOKBACK sessions, grouped
when they sit within TOL_PCT of the price or half an average true range,
whichever is wider, and kept when the cluster has MIN_TOUCHES or more.
Support is the nearest level below the close, resistance the nearest above.

Where the levels sit, not where price will go. Market Desk also derives an
entry, target and stop from them; that is a trade plan, and this site does
not publish trade plans.
"""
from __future__ import annotations

from typing import Sequence

LOOKBACK = 120
TOL_PCT = 0.75
MIN_TOUCHES = 3
# Levels further than this from the close are history, not context.
SHOWN_WITHIN_PCT = 25.0
MAX_SHOWN = 8


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
        n: int = 14) -> float | None:
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
           for i in range(1, len(closes))][-n:]
    return sum(trs) / len(trs) if trs else None


def levels(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
           lookback: int = LOOKBACK, tol_pct: float = TOL_PCT,
           min_touches: int = MIN_TOUCHES) -> list[dict]:
    """[{price, touches, sessions_ago}] sorted by price, over the last `lookback` bars."""
    h, l, c = list(highs[-lookback:]), list(lows[-lookback:]), list(closes[-lookback:])
    n = len(c)
    if n < 12:
        return []
    tol = max(tol_pct / 100 * c[-1], 0.5 * (atr(h, l, c) or 0.0))
    pivots: list[tuple[float, int]] = []
    # Strictly beyond the two bars before and at least level with the two
    # after, so a flat run yields no pivots at all.
    for i in range(2, n - 2):
        if h[i] > max(h[i - 2:i]) and h[i] >= max(h[i + 1:i + 3]):
            pivots.append((h[i], i))
        if l[i] < min(l[i - 2:i]) and l[i] <= min(l[i + 1:i + 3]):
            pivots.append((l[i], i))
    pivots.sort()
    clusters: list[list[tuple[float, int]]] = []
    current: list[tuple[float, int]] = []
    for price, i in pivots:
        if current and price - sum(p for p, _ in current) / len(current) > tol:
            clusters.append(current)
            current = []
        current.append((price, i))
    if current:
        clusters.append(current)
    found = [{"price": round(sum(p for p, _ in cl) / len(cl), 2),
              "touches": len(cl),
              "sessions_ago": n - 1 - max(i for _, i in cl)}
             for cl in clusters if len(cl) >= min_touches]
    return sorted(found, key=lambda x: x["price"])


def summary(bars) -> dict | None:
    """Support, resistance and the levels near the price, for one stock's bars."""
    rows = [b for b in bars if b.close and b.close > 0][-LOOKBACK:]
    if len(rows) < 30:
        return None
    highs = [b.high or b.close for b in rows]
    lows = [b.low or b.close for b in rows]
    closes = [b.close for b in rows]
    close = closes[-1]
    found = levels(highs, lows, closes)
    below = [x for x in found if x["price"] < close * 0.995]
    above = [x for x in found if x["price"] > close * 1.005]
    near = [x for x in found if abs(x["price"] / close - 1) * 100 <= SHOWN_WITHIN_PCT]
    near.sort(key=lambda x: abs(x["price"] - close))
    a = atr(highs, lows, closes)
    return {
        "close": round(close, 2),
        "atr": None if a is None else round(a, 2),
        "support": below[-1] if below else None,
        "resistance": above[0] if above else None,
        "levels": sorted(near[:MAX_SHOWN], key=lambda x: x["price"]),
        "lookback": LOOKBACK,
    }
