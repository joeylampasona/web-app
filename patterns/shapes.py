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
from patterns.indicators import atr, atr_pct, ema, mean, sma

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- names

SYMMETRICAL = "symmetrical_triangle"
ASCENDING = "ascending_triangle"
DESCENDING = "descending_triangle"
RISING_WEDGE = "rising_wedge"
FALLING_WEDGE = "falling_wedge"
SQUEEZE = "squeeze"

#: Which way each shape is conventionally read. See DIRECTION above.
DIRECTION = {
    SYMMETRICAL: "long",       # genuinely two-sided; treated as a continuation
    ASCENDING: "long",
    DESCENDING: "short",
    RISING_WEDGE: "short",
    FALLING_WEDGE: "long",
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


# How much room to leave beyond the far side of a shape before calling it
# broken. A stop sitting exactly on the low gets taken out by one wick on one
# thin session, which is noise rather than the structure failing.
STOP_ATR_BUFFER = 0.25


@dataclass
class Line:
    """A least-squares line through swing points, in price against bar index."""
    slope: float               # price per session
    intercept: float           # price at index 0
    touches: int
    #: The swing points the line was fitted through, as (bar index, price).
    #: Carried rather than recomputed because the chart marks exactly these —
    #: a drawn trendline that does not touch the highs it was fitted to is
    #: the single thing that makes a pattern overlay look made up.
    points: list[tuple[int, float]] = field(default_factory=list)

    def at(self, index: int) -> float:
        return self.intercept + self.slope * index

    def slope_pct(self, reference_price: float) -> float:
        """Slope as percent of price per session, so it compares across stocks."""
        if reference_price <= 0:
            return 0.0
        return 100.0 * self.slope / reference_price


def _line_json(line: "Line", bars: list[Bar], start: int, end: int) -> dict:
    """One trendline as the chart needs it: two endpoints and its touches."""
    def at(index: int) -> dict:
        index = max(0, min(index, len(bars) - 1))
        return {"date": bars[index].date.isoformat(),
                "price": round(line.at(index), 4)}

    return {
        "from": at(start),
        "to": at(end),
        "touches": [
            {"date": bars[i].date.isoformat(), "price": round(price, 4)}
            for i, price in line.points
            if 0 <= i < len(bars)
        ],
    }


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
    #: Set for squeezes only: the bands have just left the channel.
    squeeze_fired: bool = False
    #: The shape's own height in price: the pole for a flag, the widest gap
    #: between the lines for a wedge or triangle. What the measured target and
    #: therefore the reward-to-risk arithmetic is built from.
    height: float | None = None
    #: Where the shape is wrong — the far side of it, with a quarter of an
    #: average range of room so a single wick does not count as a break.
    stop: float | None = None
    #: Set for squeezes only: the TTM momentum reading on the last bar, and its
    #: five-session change. Says which way the compression is leaning, not
    #: which way it will break.
    momentum: float | None = None
    momentum_slope: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def weeks(self) -> float:
        return self.sessions / 5.0

    @property
    def apex_pct(self) -> float | None:
        """How far through its convergence, 0-1. None for a parallel shape."""
        return apex_progress(self.upper, self.lower, self.start_idx, self.end_idx)

    @property
    def target(self) -> float | None:
        return measured_target(self)

    @property
    def r_multiple(self) -> float | None:
        """Reward over risk, taking the level as the entry.

        None whenever any leg of it is missing, which is the honest answer and
        not 0.0 — a shape with no stop has undefined risk, not zero risk.
        """
        target = self.target
        if target is None or self.stop is None:
            return None
        risk = abs(self.level - self.stop)
        if risk <= 0:
            return None
        return abs(target - self.level) / risk

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
            # Drawable geometry: each line as the two prices it takes at the
            # ends of the shape, plus the swing points it passes through.
            # Published rather than left to be rebuilt in the browser from the
            # slope percentages — that reconstruction drifts, and a formation
            # overlay that misses its own highs by a percent is worse than none.
            "lines": {
                "upper": _line_json(self.upper, bars, self.start_idx, self.end_idx),
                "lower": _line_json(self.lower, bars, self.start_idx, self.end_idx),
            },
            "pole_pct": round(self.pole_pct, 2) if self.pole_pct is not None else None,
            "pole_sessions": self.pole_sessions,
            "squeeze_fired": self.squeeze_fired,
            "apex_pct": (None if self.apex_pct is None
                         else round(100.0 * self.apex_pct, 1)),
            "stale": (self.apex_pct is not None
                      and self.apex_pct > STALE_APEX_PROGRESS),
            "height_pct": (None if self.height is None or self.level <= 0
                           else round(100.0 * self.height / self.level, 2)),
            "target": None if self.target is None else round(self.target, 2),
            "stop": None if self.stop is None else round(self.stop, 2),
            "r_multiple": (None if self.r_multiple is None
                           else round(self.r_multiple, 2)),
            "momentum": None if self.momentum is None else round(self.momentum, 4),
            "momentum_slope": (None if self.momentum_slope is None
                               else round(self.momentum_slope, 4)),
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
    return Line(slope=slope, intercept=mean_y - slope * mean_x, touches=n,
                points=list(points))


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


# Past this much of the way to the apex a converging shape has run out of
# room: the lines meet, the range is already as tight as it can get, and a
# break from here is as likely to be a drift out of the wedge as a move. The
# uploaded spec puts the useful band at 50-75% and calls anything past 85%
# stale. Published, not enforced — a stale shape is still a true shape, and
# hiding it would mean a name silently leaving the screen with no reason given.
def _atr_pad(bars: list[Bar], index: int, window: int = 20) -> float:
    """A quarter of an average range at `index`, or nothing when undefined."""
    series = atr(bars[:index + 1], window)
    value = series[-1] if series else None
    return STOP_ATR_BUFFER * value if value else 0.0


def _linreg_value(values: list[float]) -> tuple[float | None, float | None]:
    """The fitted value at the last point, and the slope, of a least-squares
    line through `values` against their own position.

    This is what a charting package means by `linreg(series, n, 0)`: not the
    raw last value, and not the average, but where the trend of the last n
    points sits right now. Smoothing and direction in one pass.
    """
    n = len(values)
    if n < 2:
        return None, None
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    denom = sum((i - mean_x) ** 2 for i in range(n))
    if denom <= 0:
        return None, None
    slope = sum((i - mean_x) * (values[i] - mean_y) for i in range(n)) / denom
    return mean_y + slope * ((n - 1) - mean_x), slope


def momentum_oscillator(bars: list[Bar], window: int = 20) -> list[float | None]:
    """The TTM-style momentum reading, per bar.

    Price measured against the midpoint of its own recent range and its own
    average, then regressed. Positive is leaning up, negative down.

    It is a momentum reading and nothing more. This module refuses to say which
    way a squeeze will break — that is not something the construction knows —
    but "which way it has been leaning while compressed" is a measurement, and
    it was being left on the floor.
    """
    n = len(bars)
    out: list[float | None] = [None] * n
    if n < window:
        return out
    closes = [b.close for b in bars]
    averages = sma(closes, window)
    for i in range(window - 1, n):
        chunk = bars[i - window + 1:i + 1]
        avg = averages[i]
        if avg is None:
            continue
        donchian_mid = (max(b.high for b in chunk) + min(b.low for b in chunk)) / 2.0
        baseline = (donchian_mid + avg) / 2.0
        fitted, _ = _linreg_value([b.close - baseline for b in chunk])
        out[i] = fitted
    return out


STALE_APEX_PROGRESS = 0.85


def apex_progress(upper: Line, lower: Line, start: int, end: int) -> float | None:
    """How far through its own convergence a shape is, as 0.0 to 1.0+.

    The two lines meet at some bar; this is the share of that distance already
    travelled. None when they never meet (parallel or diverging), which is the
    normal answer for a flag and not a failure.
    """
    closing_rate = lower.slope - upper.slope
    if closing_rate <= 0:
        return None
    opening = _gap(upper, lower, start)
    if opening <= 0:
        return None
    bars_to_apex = opening / closing_rate
    if bars_to_apex <= 0:
        return None
    return (end - start) / bars_to_apex


def measured_target(shape: "Shape") -> float | None:
    """The move the shape's own height projects, from its level.

    Not a forecast. It is the conventional arithmetic — a formation that
    resolves carries about its own height — and it exists so the screen can
    compute an R multiple, which is the thing that actually filters. A target
    the shape cannot support (no height, no level) is None rather than a guess.
    """
    height = shape.height
    if height is None or height <= 0 or shape.level <= 0:
        return None
    if shape.direction == "short":
        return max(shape.level - height, 0.0)
    return shape.level + height


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
                    min_sessions: int = 10,
                    max_convergence: float = CONVERGENCE_RATIO,
                    max_volume_ratio: float | None = None) -> Shape | None:
    """The wedge or triangle price is currently inside, if there is one.

    `max_volume_ratio`, when set, requires volume inside the shape to be below
    that multiple of the fifty sessions before it. A wedge forming on rising
    volume is a different event from one forming on falling volume — the
    convergence is supposed to be the market losing interest in both
    directions — so the screens that care can ask for it.
    """
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

    if max_volume_ratio is not None:
        ratio = volume_trend(bars, start)
        if ratio is None or ratio > max_volume_ratio:
            return None

    direction = DIRECTION[kind]
    level = upper.at(end) if direction == "long" else lower.at(end)
    # A fitted line can wander outside the bars it was fitted through when the
    # swings are few and uneven. Clamping keeps the published level a price the
    # stock has actually traded near.
    level = max(min(level, high), low)

    # The widest the shape ever was, which is the height it projects. Measured
    # from the fitted lines rather than the raw extremes: a single spike out of
    # the wedge is exactly what the lines are fitted to ignore.
    widest = max(_gap(upper, lower, start), _gap(upper, lower, end), 0.0)
    pad = _atr_pad(bars, end)
    # Where the shape is wrong depends on which shape it is.
    #
    # A triangle's floor is a line that has been rising the whole time, so the
    # stop is that line where it is now, not where it was forty sessions ago.
    # Using the old low would price the risk at the full height of the shape
    # and make every triangle a one-to-one trade by construction.
    #
    # A wedge is the opposite case: both its lines slope the same way, so the
    # far line keeps running away from price and the extreme is the level that
    # actually has to hold.
    if kind in (SYMMETRICAL, ASCENDING, DESCENDING):
        boundary = lower.at(end + 1) if direction == "long" else upper.at(end + 1)
        stop = (boundary - pad) if direction == "long" else (boundary + pad)
        # Never looser than the structure itself: a line fitted through a
        # ragged floor can sit under the lowest bar in the shape.
        stop = max(stop, low - pad) if direction == "long" else min(stop, high + pad)
    else:
        stop = (low - pad) if direction == "long" else (high + pad)
    return Shape(
        kind=kind, start_idx=start, end_idx=end, upper=upper, lower=lower,
        level=level, direction=direction, convergence=ratio,
        depth_pct=100.0 * (high - low) / high,
        sessions=end - start + 1,
        height=widest or None, stop=stop,
    )


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


def keltner(bars: list[Bar], window: int = 20,
            multiple: float = 1.5) -> tuple[list[float | None], list[float | None]]:
    """Keltner channel: an EMA of the close, plus and minus N average true ranges.

    Returned as (upper, lower) aligned to the bars, None where either the EMA
    or the ATR does not exist yet.
    """
    closes = [b.close for b in bars]
    middle = ema(closes, window)
    ranges = atr(bars, window)
    upper: list[float | None] = []
    lower: list[float | None] = []
    for mid, rng in zip(middle, ranges):
        if mid is None or rng is None:
            upper.append(None)
            lower.append(None)
        else:
            upper.append(mid + multiple * rng)
            lower.append(mid - multiple * rng)
    return upper, lower


def bollinger(bars: list[Bar], window: int = 20,
              deviations: float = 2.0) -> tuple[list[float | None], list[float | None]]:
    """Bollinger bands as (upper, lower), aligned to the bars."""
    closes = [b.close for b in bars]
    middles = sma(closes, window)
    upper: list[float | None] = []
    lower: list[float | None] = []
    for i, middle in enumerate(middles):
        if middle is None or i + 1 < window:
            upper.append(None)
            lower.append(None)
            continue
        chunk = closes[i + 1 - window:i + 1]
        average = sum(chunk) / window
        sigma = (sum((c - average) ** 2 for c in chunk) / window) ** 0.5
        upper.append(middle + deviations * sigma)
        lower.append(middle - deviations * sigma)
    return upper, lower


def squeeze_states(bars: list[Bar], window: int = 20,
                   deviations: float = 2.0,
                   keltner_multiple: float = 1.5) -> list[bool | None]:
    """Per bar: are the Bollinger bands entirely inside the Keltner channel?

    True is "in squeeze". None where either band is undefined. This is the
    standard construction — volatility compressed enough that a two-sigma move
    fits inside one-and-a-half average ranges — and it replaces the earlier
    percentile version, which asked a different question: that one said "quiet
    against its own six months", this says "quiet on an absolute footing the
    same way for every name".
    """
    b_up, b_lo = bollinger(bars, window, deviations)
    k_up, k_lo = keltner(bars, window, keltner_multiple)
    out: list[bool | None] = []
    for bu, bl, ku, kl in zip(b_up, b_lo, k_up, k_lo):
        if bu is None or bl is None or ku is None or kl is None:
            out.append(None)
        else:
            out.append(bu < ku and bl > kl)
    return out


def find_squeeze(bars: list[Bar], min_sessions: int = 5,
                 window: int = 20, deviations: float = 2.0,
                 keltner_multiple: float = 1.5,
                 fired_within: int = 3) -> Shape | None:
    """A volatility compression, either still on or just released.

    Two states are reported, because they are different things to a reader:

      in squeeze   the bands are still inside the channel. Nothing has
                   happened yet and the name is worth watching.
      fired        they were inside within the last few sessions and are now
                   outside. That is the event.

    Direction is NOT claimed for either. A squeeze releasing says the range
    expanded; which way it expanded is visible in the price beside it and is
    not something the construction knows. The level published is the ceiling of
    the compressed stretch, because that is what a move up out of it clears.
    """
    n = len(bars)
    if n < window * 2:
        return None
    states = squeeze_states(bars, window, deviations, keltner_multiple)
    if states[-1] is None:
        return None

    fired = False
    if states[-1]:
        end = n - 1
    else:
        # Did it release recently? Walk back through the allowed window looking
        # for the last bar that was still compressed.
        end = None
        for back in range(1, fired_within + 1):
            index = n - 1 - back
            if index < 0:
                break
            if states[index]:
                end = index
                fired = True
                break
        if end is None:
            return None

    start = end
    while start > 0 and states[start - 1]:
        start -= 1
    sessions = end - start + 1
    if sessions < min_sessions:
        return None

    window_bars = bars[start:end + 1]
    high = max(b.high for b in window_bars)
    low = min(b.low for b in window_bars)
    if high <= 0:
        return None

    highs = [(start + i, x.high) for i, x in enumerate(window_bars)]
    lows = [(start + i, x.low) for i, x in enumerate(window_bars)]
    upper_line, lower_line = fit(highs), fit(lows)
    if upper_line is None or lower_line is None:
        return None

    # Which way the compression has been leaning. Not a claim about the break;
    # a reading of where price has sat against its own range while quiet. The
    # note names the state in the four-way form a reader can act on.
    osc = momentum_oscillator(bars, window)
    reading = osc[-1]
    slope = None
    recent = [x for x in osc[-6:] if x is not None]
    if reading is not None and len(recent) >= 2:
        slope = recent[-1] - recent[0]

    note = "released" if fired else "compressed"
    if reading is not None:
        leaning = "up" if reading > 0 else "down"
        note = f"fired {leaning}" if fired else f"compressed, leaning {leaning}"

    return Shape(
        kind=SQUEEZE, start_idx=start, end_idx=n - 1,
        upper=upper_line, lower=lower_line, level=high,
        direction=DIRECTION[SQUEEZE], convergence=1.0,
        depth_pct=100.0 * (high - low) / high, sessions=sessions,
        squeeze_fired=fired,
        # No height, therefore no target and no R multiple. A squeeze is a
        # volatility state, not a geometry: there is no measured move to
        # project, and projecting the width of the quiet stretch would be
        # inventing one. The stop is real — the floor of the compression.
        stop=low - _atr_pad(bars, n - 1),
        momentum=reading, momentum_slope=slope,
        notes=[note],
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
