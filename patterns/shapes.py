"""Converging trendlines, flags and volatility squeezes.

The six screens this site already runs all look for the same thing: a base with
a ceiling, and a price that clears it. `bases.find` locates that ceiling and
every detector hangs off it.

The shapes here are not that. A wedge and a triangle are defined by two
trendlines closing on each other, and which one you have depends on the SIGN of
each slope rather than on any ceiling. A flag is defined by what came before it
— a pole — and is meaningless without it. A squeeze is not a shape at all; it
is a statement about how quiet the range has become relative to its own recent
history.

So this module computes geometry and nothing else. It does not know about
stages, pivots, screens or staging, and it returns measurements rather than
verdicts. Whether a shape is worth showing is the detector's decision; whether
it means anything is nobody's.

DIRECTION
---------

Three of these shapes resolve downward by convention: the rising wedge, the
descending triangle and the bear flag. That is recorded in `direction` and is
the only opinion in this file, held because it decides which boundary is the
operative level — the upper line for a shape that resolves up, the lower one
for a shape that resolves down. It is not a forecast, and the site's own
disclaimer about patterns applies here exactly as it does to the bases.

NOT A CLAIM OF EDGE
-------------------

The out-of-sample work behind this site found no measurable edge in the
structural components of its base patterns; relative strength carried it. These
shapes have had no such test run against them at all — the backtest that could
have tested them measures base-and-breakout setups, not trendline convergence.
They are presented as descriptions of what the chart is doing, and the
descriptions are checkable. Nothing more is claimed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from data.types import Bar
from patterns import bases
from patterns.indicators import atr_pct, mean, sma

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- names

SYMMETRICAL = "symmetrical_triangle"
ASCENDING = "ascending_triangle"
DESCENDING = "descending_triangle"
RISING_WEDGE = "rising_wedge"
FALLING_WEDGE = "falling_wedge"
BULL_FLAG = "bull_flag"
BEAR_FLAG = "bear_flag"
SQUEEZE = "squeeze"

#: Which way each shape is conventionally read. See DIRECTION above.
DIRECTION = {
    SYMMETRICAL: "long",       # genuinely two-sided; treated as a continuation
    ASCENDING: "long",
    DESCENDING: "short",
    RISING_WEDGE: "short",
    FALLING_WEDGE: "long",
    BULL_FLAG: "long",
    BEAR_FLAG: "short",
    SQUEEZE: "long",           # directionless; the level taken is the ceiling
}

# A slope this shallow is called flat. Expressed as percent of price per
# session, so it means the same thing on a $9 stock and a $900 one. Roughly
# 1.5% over a six-week line.
FLAT_SLOPE_PCT = 0.05

# The lines must close by at least this much across the span to count as
# converging: the gap at the end no more than 70% of the gap at the start.
CONVERGENCE_RATIO = 0.70

# Below this the two lines are so nearly parallel that calling it a triangle is
# generous, and above 1.0 they are diverging.
MIN_TOUCHES_PER_LINE = 2

# How far a flag may trade beyond the end of its own pole. A flag is a pause
# at the top of a move; a window that makes a materially higher high is still
# in the move, and the pole was cut in the wrong place.
FLAG_OVERSHOOT = 0.03


@dataclass
class Line:
    """A least-squares line through swing points, in price against bar index."""
    slope: float               # price per session
    intercept: float           # price at index 0
    touches: int

    def at(self, index: int) -> float:
        return self.intercept + self.slope * index

    def slope_pct(self, reference_price: float) -> float:
        """Slope as percent of price per session, so it compares across stocks."""
        if reference_price <= 0:
            return 0.0
        return 100.0 * self.slope / reference_price


@dataclass
class Shape:
    kind: str
    start_idx: int
    end_idx: int
    upper: Line
    lower: Line
    #: The boundary that matters: the upper line for a shape read upward, the
    #: lower line for one read downward. Evaluated at the last bar of the shape.
    level: float
    direction: str
    #: How much the lines closed: 0.0 is a perfect point, 1.0 is parallel.
    convergence: float
    depth_pct: float
    sessions: int
    #: Set for flags only — how far the pole ran, and over how long.
    pole_pct: float | None = None
    pole_sessions: int | None = None
    #: Set for squeezes only — where current bandwidth sits in its own history.
    squeeze_percentile: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def weeks(self) -> float:
        return self.sessions / 5.0

    def to_json(self, bars: list[Bar]) -> dict:
        return {
            "kind": self.kind,
            "start": bars[self.start_idx].date.isoformat(),
            "end": bars[self.end_idx].date.isoformat(),
            "level": round(self.level, 2),
            "direction": self.direction,
            "convergence": round(self.convergence, 3),
            "depth_pct": round(self.depth_pct, 2),
            "weeks": round(self.weeks, 1),
            "upper_slope_pct": round(self.upper.slope_pct(self.level), 4),
            "lower_slope_pct": round(self.lower.slope_pct(self.level), 4),
            "touches": {"upper": self.upper.touches, "lower": self.lower.touches},
            "pole_pct": round(self.pole_pct, 2) if self.pole_pct is not None else None,
            "pole_sessions": self.pole_sessions,
            "squeeze_percentile": (round(self.squeeze_percentile, 1)
                                   if self.squeeze_percentile is not None else None),
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------- fitting

def fit(points: list[tuple[int, float]]) -> Line | None:
    """Least squares through (index, price). None when it cannot be determined.

    Two points give an exact line, which is the minimum a trendline can be drawn
    from and also the minimum at which "trendline" starts to flatter the thing.
    The touch count travels with the line so a caller can prefer three.
    """
    n = len(points)
    if n < MIN_TOUCHES_PER_LINE:
        return None
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    denominator = sum((p[0] - mean_x) ** 2 for p in points)
    if denominator <= 0:                      # every point on the same bar
        return None
    slope = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points) / denominator
    return Line(slope=slope, intercept=mean_y - slope * mean_x, touches=n)


def _gap(upper: Line, lower: Line, index: int) -> float:
    return upper.at(index) - lower.at(index)


def convergence(upper: Line, lower: Line, start: int, end: int) -> float | None:
    """Gap at the end as a fraction of the gap at the start.

    Below 1.0 the lines are closing, above 1.0 they are spreading. None when the
    opening gap is not positive, which means the fit is degenerate rather than
    narrow — two lines that already cross have nothing to say about convergence.
    """
    opening = _gap(upper, lower, start)
    if opening <= 0:
        return None
    closing = _gap(upper, lower, end)
    return max(closing, 0.0) / opening


# ---------------------------------------------------------------- shapes

def _swing_points(bars: list[Bar], start: int, end: int,
                  threshold_pct: float) -> tuple[list, list]:
    """Swing highs and swing lows over the window, as (index, price) pairs."""
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for index, kind in bases.swings(bars, start, end, threshold_pct):
        if kind == "H":
            highs.append((index, bars[index].high))
        else:
            lows.append((index, bars[index].low))
    return highs, lows


def classify(upper: Line, lower: Line, reference_price: float) -> str | None:
    """Which converging shape the two slopes describe.

    The sign of each slope is the whole classification. A flat upper line with a
    rising lower one is an ascending triangle; both falling with the lower
    falling slower is a falling wedge; and so on. Returns None for the
    combination that is none of them — both lines moving the same way at the
    same rate, which is a channel rather than a wedge.
    """
    up = upper.slope_pct(reference_price)
    low = lower.slope_pct(reference_price)
    up_flat = abs(up) < FLAT_SLOPE_PCT
    low_flat = abs(low) < FLAT_SLOPE_PCT

    if up_flat and low > 0:
        return ASCENDING
    if low_flat and up < 0:
        return DESCENDING
    if up < 0 and low > 0:
        return SYMMETRICAL
    if up > 0 and low > 0:
        # Converging while both rise: the lows are catching the highs.
        return RISING_WEDGE if low > up else None
    if up < 0 and low < 0:
        # Converging while both fall: the highs are falling faster.
        return FALLING_WEDGE if up < low else None
    return None


def find_converging(bars: list[Bar], lookback: int, threshold_pct: float = 3.0,
                    min_sessions: int = 15,
                    max_convergence: float = CONVERGENCE_RATIO) -> Shape | None:
    """The wedge or triangle price is currently inside, if there is one."""
    n = len(bars)
    if n < min_sessions + 5:
        return None
    start = max(0, n - 1 - lookback)
    end = n - 1
    if end - start < min_sessions:
        return None

    highs, lows = _swing_points(bars, start, end, threshold_pct)
    upper, lower = fit(highs), fit(lows)
    if upper is None or lower is None:
        return None

    ratio = convergence(upper, lower, start, end)
    if ratio is None or ratio > max_convergence:
        return None

    reference = bars[end].close
    kind = classify(upper, lower, reference)
    if kind is None:
        return None

    window = bars[start:end + 1]
    high = max(b.high for b in window)
    low = min(b.low for b in window)
    if high <= 0:
        return None

    direction = DIRECTION[kind]
    level = upper.at(end) if direction == "long" else lower.at(end)
    # A fitted line can wander outside the bars it was fitted through when the
    # swings are few and uneven. Clamping keeps the published level a price the
    # stock has actually traded near.
    level = max(min(level, high), low)

    return Shape(
        kind=kind, start_idx=start, end_idx=end, upper=upper, lower=lower,
        level=level, direction=direction, convergence=ratio,
        depth_pct=100.0 * (high - low) / high,
        sessions=end - start + 1,
    )


def find_flag(bars: list[Bar], max_flag_sessions: int = 15,
              min_flag_sessions: int = 3, min_pole_pct: float = 15.0,
              max_pole_sessions: int = 20,
              max_retrace: float = 0.50,
              bullish: bool = True) -> Shape | None:
    """A sharp run, then a shallow drift against it.

    The pole is the point. A three-week sideways drift with nothing in front of
    it is a pause, not a flag, and the thing that makes a flag worth naming is
    that it interrupts a move rather than that it is narrow. So the pole is
    measured first and the drift is only examined if one is there.

    The drift must also go the RIGHT way: a bull flag drifts down or sideways
    after a rise. A drift that keeps rising is not a flag, it is the advance
    continuing, and calling it a flag would put every strong stock on the screen.
    """
    n = len(bars)
    if n < max_pole_sessions + min_flag_sessions + 2:
        return None

    best: Shape | None = None
    for flag_len in range(min_flag_sessions, max_flag_sessions + 1):
        flag_start = n - flag_len
        pole_end = flag_start - 1
        if pole_end <= 0:
            break
        for pole_len in range(5, max_pole_sessions + 1):
            pole_start = pole_end - pole_len
            if pole_start < 0:
                break
            a = bars[pole_start].close
            b = bars[pole_end].close
            if a <= 0:
                continue
            move = 100.0 * (b / a - 1.0)
            if bullish and move < min_pole_pct:
                continue
            if not bullish and move > -min_pole_pct:
                continue

            flag_bars = bars[flag_start:]
            flag_high = max(x.high for x in flag_bars)
            flag_low = min(x.low for x in flag_bars)
            pole_span = abs(b - a)
            if pole_span <= 0:
                continue

            # How much of the pole the drift has given back.
            retrace = ((b - flag_low) / pole_span if bullish
                       else (flag_high - b) / pole_span)
            if retrace < 0 or retrace > max_retrace:
                continue

            # The pole has to end at the pole's own extreme. Without this the
            # window can be cut mid-advance: a "pole" ending halfway up the
            # rally, and a "flag" that then swallows the rest of the rally AND
            # the collapse after it. That case reached a retrace of exactly
            # 0.50 by coincidence and was published as a bull flag — a 25-point
            # decline wearing the name of a consolidation.
            if bullish and flag_high > b * (1.0 + FLAG_OVERSHOOT):
                continue
            if not bullish and flag_low < b * (1.0 - FLAG_OVERSHOOT):
                continue

            # And that it drifts against the pole rather than extending it.
            last = flag_bars[-1].close
            if bullish and last > flag_bars[0].high:
                continue
            if not bullish and last < flag_bars[0].low:
                continue

            highs = [(flag_start + i, x.high) for i, x in enumerate(flag_bars)]
            lows = [(flag_start + i, x.low) for i, x in enumerate(flag_bars)]
            upper, lower = fit(highs), fit(lows)
            if upper is None or lower is None:
                continue

            kind = BULL_FLAG if bullish else BEAR_FLAG
            direction = DIRECTION[kind]
            level = flag_high if bullish else flag_low
            shape = Shape(
                kind=kind, start_idx=flag_start, end_idx=n - 1,
                upper=upper, lower=lower, level=level, direction=direction,
                convergence=1.0,           # a flag is a channel, not a wedge
                depth_pct=(100.0 * (flag_high - flag_low) / flag_high
                           if flag_high > 0 else 0.0),
                sessions=flag_len,
                pole_pct=move, pole_sessions=pole_len,
            )
            # Prefer the biggest pole: the same drift after a 40% run is a more
            # distinctive thing than after a 16% one.
            if best is None or abs(move) > abs(best.pole_pct or 0.0):
                best = shape
    return best


def bandwidth(bars: list[Bar], window: int = 20,
              deviations: float = 2.0) -> list[float | None]:
    """Bollinger bandwidth: the band's width as a fraction of its middle.

    Written out rather than imported because the site carries no numeric stack
    in its core, and a twenty-bar standard deviation is four lines.
    """
    closes = [b.close for b in bars]
    middles = sma(closes, window)
    out: list[float | None] = []
    for i, middle in enumerate(middles):
        if middle is None or middle <= 0 or i + 1 < window:
            out.append(None)
            continue
        chunk = closes[i + 1 - window:i + 1]
        average = sum(chunk) / window
        variance = sum((c - average) ** 2 for c in chunk) / window
        sigma = variance ** 0.5
        out.append((2 * deviations * sigma) / middle)
    return out


def find_squeeze(bars: list[Bar], lookback: int = 126,
                 percentile: float = 15.0, window: int = 20) -> Shape | None:
    """Range compression: bandwidth near the quietest it has been in months.

    Not a shape and not a direction. It says the stock has stopped moving
    relative to its own recent history, which is a fact about the range and
    nothing else — the common claim that a squeeze must "resolve" in a
    particular direction is not something this can see and not something it
    says. The level published is the ceiling of the quiet stretch, because that
    is the price a move out of it would have to clear.
    """
    n = len(bars)
    if n < lookback // 2:
        return None
    widths = bandwidth(bars, window)
    current = widths[-1]
    if current is None:
        return None
    history = [w for w in widths[-lookback:] if w is not None]
    if len(history) < 30:
        return None

    rank = 100.0 * sum(1 for w in history if w <= current) / len(history)
    if rank > percentile:
        return None

    # How long it has been quiet: back to the last bar wider than the threshold.
    cutoff = sorted(history)[max(0, int(len(history) * percentile / 100.0) - 1)]
    start = n - 1
    while start > 0:
        w = widths[start - 1]
        if w is None or w > cutoff:
            break
        start -= 1
    sessions = n - start
    if sessions < window // 2:
        return None

    window_bars = bars[start:]
    high = max(b.high for b in window_bars)
    low = min(b.low for b in window_bars)
    if high <= 0:
        return None

    highs = [(start + i, x.high) for i, x in enumerate(window_bars)]
    lows = [(start + i, x.low) for i, x in enumerate(window_bars)]
    upper, lower = fit(highs), fit(lows)
    if upper is None or lower is None:
        return None

    return Shape(
        kind=SQUEEZE, start_idx=start, end_idx=n - 1, upper=upper, lower=lower,
        level=high, direction=DIRECTION[SQUEEZE], convergence=1.0,
        depth_pct=100.0 * (high - low) / high, sessions=sessions,
        squeeze_percentile=rank,
    )


def volume_trend(bars: list[Bar], start_idx: int) -> float | None:
    """Mean volume inside the shape against the fifty sessions before it.

    Below 1.0 means the shape is quieter than what led into it, which is the
    usual description of a healthy consolidation. It is reported rather than
    required: a screen that insisted on it would drop shapes that are otherwise
    exactly what was asked for, and the number is more use than the filter.
    """
    inside = [b.volume for b in bars[start_idx:] if b.volume]
    before = [b.volume for b in bars[max(0, start_idx - 50):start_idx] if b.volume]
    if not inside or not before:
        return None
    prior = mean(before)
    if prior <= 0:
        return None
    return mean(inside) / prior


def atr_compression(bars: list[Bar], start_idx: int) -> float | None:
    """ATR inside the shape against the fifty sessions before it. Below 1 is calmer."""
    series = atr_pct(bars, 14)
    inside = [v for v in series[start_idx:] if v is not None]
    before = [v for v in series[max(0, start_idx - 50):start_idx] if v is not None]
    if not inside or not before:
        return None
    prior = mean(before)
    if prior <= 0:
        return None
    return mean(inside) / prior
