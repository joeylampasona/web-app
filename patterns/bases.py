"""Base and pivot structure: where the ceiling is, and what happened under it."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from data.types import Bar

STALE_BREAKOUT_SESSIONS = 252     # a breakout older than a year is not this base


@dataclass
class Contraction:
    start: dt.date
    end: dt.date
    high: float
    low: float
    depth_pct: float
    weeks: float

    def to_json(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(),
                "high": round(self.high, 2), "low": round(self.low, 2),
                "depth_pct": round(self.depth_pct, 2), "weeks": round(self.weeks, 1)}


@dataclass
class Structure:
    start_idx: int
    end_idx: int
    pivot: float
    depth_pct: float
    weeks: float
    low: float
    contractions: list[Contraction] = field(default_factory=list)
    breakout_idx: int | None = None

    def to_json(self, bars: list[Bar]) -> dict:
        return {
            "start": bars[self.start_idx].date.isoformat(),
            "end": bars[self.end_idx].date.isoformat(),
            "pivot": round(self.pivot, 2),
            "low": round(self.low, 2),
            "depth_pct": round(self.depth_pct, 2),
            "weeks": round(self.weeks, 1),
            "breakout_date": (bars[self.breakout_idx].date.isoformat()
                              if self.breakout_idx is not None else None),
            "contractions": [c.to_json() for c in self.contractions],
        }


def swings(bars: list[Bar], start: int, end: int, threshold_pct: float) -> list[tuple[int, str]]:
    """A zigzag over [start, end]: alternating swing highs and lows."""
    if end <= start:
        return []
    points: list[tuple[int, str]] = []
    direction = "up"
    extreme = start
    for i in range(start + 1, end + 1):
        if direction == "up":
            if bars[i].high >= bars[extreme].high:
                extreme = i
            elif bars[extreme].high > 0 and \
                    100.0 * (bars[extreme].high - bars[i].low) / bars[extreme].high >= threshold_pct:
                points.append((extreme, "H"))
                direction, extreme = "down", i
        else:
            if bars[i].low <= bars[extreme].low:
                extreme = i
            elif bars[extreme].low > 0 and \
                    100.0 * (bars[i].high - bars[extreme].low) / bars[extreme].low >= threshold_pct:
                points.append((extreme, "L"))
                direction, extreme = "up", i
    points.append((extreme, "H" if direction == "up" else "L"))
    return points


MAX_CONTRACTIONS = 6


def contractions(bars: list[Bar], start: int, end: int, threshold_pct: float,
                 pivot: float) -> list[Contraction]:
    """Each pullback inside the base, in order.

    The swing threshold is scaled against the depth of the base itself, so a
    wide base reports its handful of real pullbacks rather than every wiggle.
    """
    out: list[Contraction] = []
    low_of_base = min(b.low for b in bars[start:end + 1])
    depth = 100.0 * (pivot - low_of_base) / pivot if pivot else 0.0
    threshold_pct = max(threshold_pct, 0.30 * depth)
    points = swings(bars, start, end, threshold_pct)
    for (i, kind), (j, next_kind) in zip(points, points[1:]):
        if kind != "H" or next_kind != "L":
            continue
        high, low = bars[i].high, bars[j].low
        if high <= 0:
            continue
        out.append(Contraction(
            start=bars[i].date, end=bars[j].date, high=high, low=low,
            depth_pct=100.0 * (high - low) / high,
            weeks=(j - i + 1) / 5.0))
    if not out:
        low = min(b.low for b in bars[start:end + 1])
        out.append(Contraction(
            start=bars[start].date, end=bars[end].date, high=pivot, low=low,
            depth_pct=100.0 * (pivot - low) / pivot if pivot else 0.0,
            weeks=(end - start + 1) / 5.0))
    return out[-MAX_CONTRACTIONS:]


def _structure_from(bars: list[Bar], start: int, end: int, pivot: float,
                    threshold_pct: float, breakout_idx: int | None) -> Structure:
    low = min(b.low for b in bars[start:end + 1])
    return Structure(
        start_idx=start, end_idx=end, pivot=pivot,
        depth_pct=100.0 * (pivot - low) / pivot if pivot else 0.0,
        weeks=(end - start + 1) / 5.0,
        low=low,
        contractions=contractions(bars, start, end, threshold_pct, pivot),
        breakout_idx=breakout_idx)


def _forming_candidate(bars: list[Bar], highs: list[float], window: int, n: int,
                       threshold_pct: float, min_base_sessions: int) -> Structure | None:
    lo = max(0, n - window)
    segment = highs[lo:n]
    pivot = max(segment)
    start = lo + segment.index(pivot)
    end = n - 1
    if end - start + 1 < min_base_sessions:
        return None
    return _structure_from(bars, start, end, pivot, threshold_pct, None)


def find(bars: list[Bar], lookback_sessions: int, threshold_pct: float = 3.0,
         min_base_sessions: int = 15) -> Structure | None:
    """The base that matters now: the one being built, or the one just cleared.

    Two candidates are considered. The first is the stretch since the highest
    high of the lookback window — a base still forming. The second is the most
    recent breakout with a long enough stretch behind it; candidates are walked
    back from today because a stock making new highs every few days has not yet
    built anything, and reporting a two-day base for it would be nonsense.

    When both exist the newer structure wins, unless price has fallen back under
    the older pivot — at which point that older breakout is the thing that
    happened, and the setup belongs in played out rather than quietly becoming
    a fresh base.
    """
    n = len(bars)
    if n < 25:
        return None
    highs = [b.high for b in bars]
    closes = [b.close for b in bars]
    window = max(15, min(lookback_sessions, n - 1))

    forming = _forming_candidate(bars, highs, window, n, threshold_pct, min_base_sessions)

    broken: Structure | None = None
    for i in range(n - 1, window - 1, -1):
        if (n - 1 - i) > STALE_BREAKOUT_SESSIONS:
            break
        lo = i - window
        segment = highs[lo:i]
        lid = max(segment)
        if not (closes[i] > lid and closes[i - 1] <= lid):
            continue
        start = lo + segment.index(lid)
        end = i - 1
        if end - start + 1 < min_base_sessions:
            continue
        broken = _structure_from(bars, start, end, lid, threshold_pct, i)
        break

    if forming and broken:
        newer = forming.start_idx > (broken.breakout_idx or 0)
        if newer and closes[-1] > broken.pivot:
            return forming
        return broken
    return forming or broken


def history(bars: list[Bar], lookback_sessions: int, threshold_pct: float = 3.0,
            limit: int = 12, min_base_sessions: int = 15) -> list[Structure]:
    """Every base this stock has built in the history we hold — for the X-ray."""
    n = len(bars)
    highs = [b.high for b in bars]
    closes = [b.close for b in bars]
    window = max(15, min(lookback_sessions, max(15, n // 3)))
    out: list[Structure] = []
    i = window
    while i < n:
        lo = i - window
        lid = max(highs[lo:i])
        if closes[i] > lid and closes[i - 1] <= lid:
            segment = highs[lo:i]
            start = lo + segment.index(lid)
            end = i - 1
            if end - start + 1 >= min_base_sessions:
                out.append(_structure_from(bars, start, end, lid, threshold_pct, i))
            i += 20                     # one thrust is one base, not twenty
        else:
            i += 1
    current = find(bars, lookback_sessions, threshold_pct, min_base_sessions)
    if current and (not out or current.start_idx != out[-1].start_idx):
        out.append(current)
    return out[-limit:]
