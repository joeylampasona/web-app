"""A price shape small enough to ship in a list.

A sparkline needs the shape of the last few weeks, not the prices. So the
series is normalised to whole numbers from 0 to 100 across its own range and
the actual values are dropped: the renderer only ever asks "how high is this
point relative to the rest", which is the one question a 60-pixel line can
answer. Normalised integers are roughly half the bytes of rounded prices, and
the search index carries one per name.

The direction is kept separately, because a normalised series cannot tell you
whether the stock went up -- both a doubling and a halving normalise to a line
that ends at 100 or at 0 with no unit attached.
"""
from __future__ import annotations

from collections.abc import Sequence

# Thirty points across six weeks of sessions. A sparkline is drawn about sixty
# pixels wide, so more points would be sub-pixel detail nobody can see and
# everybody downloads.
POINTS = 30


def shape(closes: Sequence[float]) -> list[int] | None:
    """Normalised 0-100 series, or None when there is nothing to draw.

    Returns None rather than a flat line when the window has no range at all.
    A dead-flat sparkline and a missing one look identical to a reader, and
    only one of them is honest: a stock that did not move and a stock we have
    no data for are not the same thing, so the caller can label them apart.
    """
    window = [c for c in closes[-POINTS:] if c is not None]
    if len(window) < 2:
        return None
    lo, hi = min(window), max(window)
    span = hi - lo
    if span <= 0:
        return None
    return [round((c - lo) / span * 100) for c in window]


def change_pct(closes: Sequence[float]) -> float | None:
    """Move across the same window the shape covers, in per cent."""
    window = [c for c in closes[-POINTS:] if c is not None]
    if len(window) < 2 or not window[0]:
        return None
    return round((window[-1] - window[0]) / window[0] * 100, 2)
