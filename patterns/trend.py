"""Moving-average alignment: 9 / 21 / 50 / 200.

Simple, not exponential, because the rest of the site is. The stage classifier
already trails on a 50-day SMA and two screens already gate on the 50 and the
200; adding an exponential 50 would put two different fifty-day lines on the
same chart meaning different things, which is the kind of quiet inconsistency
that makes a tool untrustworthy.

Why these four, and why this matters here: until now nothing on this site
measured anything shorter than about a quarter. The shortest trend line was the
50-day and the shortest relative-strength window is three months, so a stock
could be rated 95, sit above its 50 and its 200, and have been rolling over for
three weeks without the site noticing. The 9 and the 21 are about two and four
weeks; they are the part that is genuinely new.

The 100 is deliberately absent. It sits between the 50 and the 200 and tells you
almost nothing neither of them does.

**Cooling is not the same as finished.** A 9 crossing below a 21 is often a
pause inside a move that then continues. It is reported as a marker on setups
that have already broken out, and it does not decide what counts as played out —
that still belongs to the 50-day line, which is a slower and surer answer.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from patterns.indicators import sma

# Fast to slow. The order is the whole point: each must sit above the next.
WINDOWS = (9, 21, 50, 200)

# How recently the 9 crossed under the 21 for it to still be news. Two weeks:
# long enough to catch it, short enough that it is about now.
COOLING_SESSIONS = 10


@dataclass
class Alignment:
    """Where a stock sits against its own moving averages, on one day."""
    values: dict[int, float | None]
    #: How many of the three rungs (9>21, 21>50, 50>200) hold. 3 is a full stack.
    rungs: int
    stacked: bool
    price_above_all: bool
    #: Sessions the stack has held unbroken, or None when it is not stacked.
    #: Newly stacked and stacked-since-spring are different states and nothing
    #: else on this site measures the duration of anything.
    stacked_sessions: int | None
    #: The 9 closed under the 21 within the last COOLING_SESSIONS.
    cooling: bool

    def to_json(self) -> dict:
        return {
            "sma": {str(w): (round(v, 2) if v is not None else None)
                    for w, v in self.values.items()},
            "rungs": self.rungs,
            "stacked": self.stacked,
            "price_above_all": self.price_above_all,
            "stacked_sessions": self.stacked_sessions,
            "cooling": self.cooling,
        }


def series(closes: Sequence[float]) -> dict[int, list[float | None]]:
    """Every window, computed once, so nothing recomputes a 200-day average."""
    return {window: sma(closes, window) for window in WINDOWS}


def _rungs_at(lines: dict[int, list[float | None]], i: int) -> int | None:
    """How many of 9>21, 21>50, 50>200 hold. None when history is too short."""
    got = [lines[w][i] for w in WINDOWS]
    if any(v is None for v in got):
        return None
    return sum(1 for a, b in zip(got, got[1:]) if a > b)


def alignment(closes: Sequence[float],
              lines: dict[int, list[float | None]] | None = None,
              index: int = -1) -> Alignment | None:
    """Alignment on one session, or None when there is not enough history.

    A stock with under 200 sessions has no 200-day average, and reporting it as
    "not stacked" would be a claim rather than an absence.
    """
    if not closes:
        return None
    lines = lines or series(closes)
    i = index if index >= 0 else len(closes) + index
    if not (0 <= i < len(closes)):
        return None

    rungs = _rungs_at(lines, i)
    if rungs is None:
        return None
    values = {w: lines[w][i] for w in WINDOWS}
    stacked = rungs == len(WINDOWS) - 1
    above = all(v is not None and closes[i] > v for v in values.values())

    held: int | None = None
    if stacked:
        held = 0
        j = i
        while j >= 0 and _rungs_at(lines, j) == len(WINDOWS) - 1:
            held += 1
            j -= 1

    fast, slow = lines[WINDOWS[0]], lines[WINDOWS[1]]
    cooling = False
    for j in range(max(1, i - COOLING_SESSIONS + 1), i + 1):
        a, b = fast[j], slow[j]
        prev_a, prev_b = fast[j - 1], slow[j - 1]
        if None in (a, b, prev_a, prev_b):
            continue
        if prev_a >= prev_b and a < b:
            cooling = True
            break

    return Alignment(values=values, rungs=rungs, stacked=stacked,
                     price_above_all=above, stacked_sessions=held,
                     cooling=cooling)


DESCRIPTIONS = {
    "cooling": "The 9-day average crossed below the 21-day in the last two weeks. "
               "Short-term momentum has eased. That is often a pause inside a move "
               "rather than the end of one, which is why it is a marker and not a "
               "stage.",
    "stacked": "The 9, 21, 50 and 200-day averages are in order, fastest above "
               "slowest. Every timeframe agrees on the direction.",
}
