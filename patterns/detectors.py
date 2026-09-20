"""Four detectors. Each is a pure function of (series, params) and returns a
structured result or None. Every threshold comes from the params object.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any

from data.types import Bar
from patterns import bases, flags, shapes as shapemod, stages, trend
from patterns.indicators import atr_pct, mean, sma
from patterns.params import Params


@dataclass
class Series:
    """Everything a detector is allowed to know about one stock."""
    symbol: str
    bars: list[Bar]
    rs_rating: int | str = "not ranked yet"
    list_date: dt.date | None = None
    name: str = ""


@dataclass
class Setup:
    symbol: str
    name: str
    screen: str
    stage: str
    pivot: float
    close: float
    bases: list[dict] = field(default_factory=list)
    rs_rating: Any = "not ranked yet"
    now_vs_pivot_pct: float | None = None
    tightening_atr_ratio: float | None = None
    volume_dryup_ratio: float | None = None
    up_down_volume_net: float | None = None
    from_52w_high_pct: float | None = None
    price_vs_50ma_pct: float | None = None
    base_weeks: float | None = None
    base_depth_pct: float | None = None
    flags: list[str] = field(default_factory=list)
    quadrant: str | None = None
    breakout_date: str | None = None
    sessions_since_breakout: int | None = None
    breakout_metrics: dict = field(default_factory=dict)
    prior_breakout: dict | None = None
    base_history: list[dict] = field(default_factory=list)
    catalysts: dict = field(default_factory=dict)
    themes: list[str] = field(default_factory=list)
    industry: str = ""
    volume: float | None = None
    ohlc: dict = field(default_factory=dict)
    #: Where the stock sits against its 9/21/50/200-day averages. None when it
    #: has under 200 sessions of history — an absence, not a failing grade.
    trend: dict | None = None
    #: "long" or "short". Which way this screen reads its own level. Every
    #: base screen is long; the wedge, triangle and flag screens are whichever
    #: their shape is. Anything that counts breakouts site-wide has to filter
    #: on it, or a bear flag resolving downward is counted as a breakout up.
    direction: str = "long"
    #: The fitted geometry, for the shape screens. None for the base screens.
    shape: dict | None = None
    #: Last session's volume against the prior fifty. 1.0 is an ordinary day.
    rvol: float | None = None
    #: Heavy volume, a decisive close and a real gain, all in the last bar.
    #: None when there is too little history to say.
    ignition: dict | None = None
    #: How many of the published checks line up, and which. Never a percentage
    #: — see the note above `criteria`.
    criteria: dict | None = None

    def to_json(self) -> dict:
        out = asdict(self)
        # Every base this stock has ever built is for the X-ray, and the X-ray
        # reads it from the top level of the stock file, where it is written
        # once. Carried inside each setup as well it was 45% of every screen
        # file — 396KB on the VCP screen alone — shipped to every reader of a
        # page that does not contain the feature.
        out.pop("base_history", None)
        return out


# ---------------------------------------------------------------- metrics

def _half_ratios(bars: list[Bar], start: int, end: int) -> tuple[float | None, float | None]:
    """(tightening, volume dry-up), both reported so that larger means calmer."""
    span = end - start + 1
    if span < 10:
        return None, None
    mid = start + span // 2
    ranges = atr_pct(bars, 5)
    first_atr = [r for r in ranges[start:mid] if r is not None]
    second_atr = [r for r in ranges[mid:end + 1] if r is not None]
    first_vol = [b.volume for b in bars[start:mid]]
    second_vol = [b.volume for b in bars[mid:end + 1]]
    tight = (mean(first_atr) / mean(second_atr)
             if first_atr and second_atr and mean(second_atr) > 0 else None)
    dry = (mean(first_vol) / mean(second_vol)
           if first_vol and second_vol and mean(second_vol) > 0 else None)
    return tight, dry


def _up_down_volume_net(bars: list[Bar], window: int = 50) -> float | None:
    recent = bars[-window:]
    if len(recent) < 10:
        return None
    up = down = 0.0
    for i in range(1, len(recent)):
        if recent[i].close > recent[i - 1].close:
            up += recent[i].volume
        elif recent[i].close < recent[i - 1].close:
            down += recent[i].volume
    total = up + down
    return (up - down) / total if total else None


def _breakout_metrics(bars: list[Bar], idx: int, ma50: list[float | None]) -> dict:
    bar = bars[idx]
    prev = bars[idx - 1] if idx else bar
    normal = mean([b.volume for b in bars[max(0, idx - 50):idx]]) or 1.0
    line = ma50[idx]
    return {
        "breakout_day_gain_pct": round(100.0 * (bar.close / prev.close - 1.0), 2)
        if prev.close else None,
        "one_day_gain_pct": round(100.0 * (bars[-1].close / bars[-2].close - 1.0), 2)
        if len(bars) > 1 and bars[-2].close else None,
        "breakout_volume_multiple": round(bar.volume / normal, 2),
        "close_in_range": round(flags.close_in_range(bar), 2),
        "price_vs_50ma_pct": round(100.0 * (bars[-1].close / line - 1.0), 2) if line else None,
        "date": bar.date.isoformat(),
    }


# ---------------------------------------------------------------- criteria
#
# WHAT THIS IS NOT: a confidence percentage.
#
# A number like "78% confident" asserts a probability, and this site has none
# to offer. The out-of-sample work behind it found no measurable edge in the
# structural parts of these patterns — only in relative strength — and the
# backtest that could have measured a composite score was removed as a page and
# never scored one anyway. Printing a percentage would be inventing a
# probability and attaching this site's name to it.
#
# So it counts, and it names what it counted. "Six of nine" is the same
# information a percentage would carry, minus the claim, and the reader can see
# WHICH six — which is the part that is actually useful, because a setup
# missing "above its 200-day" is a different thing from one missing "volume has
# dried up" even at the same tally.
#
# Every criterion below is a fact already published on the card. Nothing here
# computes anything new; it collects what is already shown and says how much of
# it lines up.

CRITERIA_LABELS = {
    "rs_leader": "Relative strength of 80 or better",
    "above_50ma": "Above its 50-day line",
    "above_200ma": "Above its 200-day line",
    "full_stack": "Averages fully stacked",
    "near_pivot": "Within 5% of its pivot",
    "tightening": "Range tightening through the base",
    "volume_dryup": "Volume drying up through the base",
    "accumulation": "More up-volume than down-volume",
    "near_highs": "Within 15% of its 52-week high",
}

#: An RS of 80 rather than the screen's own floor. This asks "is it a leader",
#: which is a fixed question; the screen's min_rs is a dial the reader moves.
CRITERIA_RS = 80
CRITERIA_NEAR_PIVOT_PCT = 5.0
CRITERIA_NEAR_HIGH_PCT = 15.0


def criteria(setup: Setup, alignment) -> dict:
    """Which of the published checks this setup currently meets.

    A criterion that cannot be evaluated is left out of BOTH the tally and the
    total rather than counted as failed. A stock with under 200 sessions has no
    200-day average, and scoring it as "not above its 200-day" would be a claim
    about a line that does not exist — the same absence-is-not-a-failing-grade
    rule the trend panel already follows.
    """
    checks: dict[str, bool] = {}

    rs = setup.rs_rating
    if isinstance(rs, int):
        checks["rs_leader"] = rs >= CRITERIA_RS
    if setup.price_vs_50ma_pct is not None:
        checks["above_50ma"] = setup.price_vs_50ma_pct > 0
    if alignment is not None:
        values = alignment.values
        if values.get(200) is not None:
            checks["above_200ma"] = setup.close > values[200]
        checks["full_stack"] = alignment.stacked
    if setup.now_vs_pivot_pct is not None:
        checks["near_pivot"] = abs(setup.now_vs_pivot_pct) <= CRITERIA_NEAR_PIVOT_PCT
    if setup.tightening_atr_ratio is not None:
        checks["tightening"] = setup.tightening_atr_ratio > 1.0
    if setup.volume_dryup_ratio is not None:
        checks["volume_dryup"] = setup.volume_dryup_ratio > 1.0
    if setup.up_down_volume_net is not None:
        checks["accumulation"] = setup.up_down_volume_net > 0
    if setup.from_52w_high_pct is not None:
        checks["near_highs"] = setup.from_52w_high_pct <= CRITERIA_NEAR_HIGH_PCT

    met = [k for k, v in checks.items() if v]
    return {
        "met": len(met),
        "total": len(checks),
        "checks": [{"key": k, "label": CRITERIA_LABELS[k], "met": v}
                   for k, v in checks.items()],
    }


# ---------------------------------------------------------------- ignition
#
# "Real time" is not available here and never will be: the site is rebuilt once
# a night from end-of-day bars. What IS available is the session that just
# closed, and a volume surge in it is not a fifteen-minute event — it is a fact
# about the day that stays true. So this measures the last completed bar and
# says so, rather than implying a live tape.

#: Volume against the prior fifty sessions. 1.0 is an ordinary day.
IGNITION_VOLUME = 2.0
#: Where the close sat in the day's range. Near 1.0 means it closed on its high.
IGNITION_CLOSE_IN_RANGE = 0.70
#: And it has to have gone somewhere. Heavy volume on an unchanged close is
#: churn, which is a different thing and reads as the opposite of ignition.
IGNITION_GAIN_PCT = 2.0


def relative_volume(bars: list[Bar], window: int = 50) -> float | None:
    """The last session's volume against the average of the ones before it."""
    if len(bars) < 10:
        return None
    prior = [b.volume for b in bars[max(0, len(bars) - 1 - window):len(bars) - 1]
             if b.volume]
    if not prior:
        return None
    normal = mean(prior)
    if normal <= 0:
        return None
    return bars[-1].volume / normal


def ignition(bars: list[Bar]) -> dict | None:
    """A heavy, decisive up-session in the bar that just closed.

    All three tests, not any of them. Heavy volume alone is as often
    distribution as accumulation; a close on the high with no volume behind it
    is a quiet drift. The combination is the thing worth marking.
    """
    if len(bars) < 12:
        return None
    rvol = relative_volume(bars)
    if rvol is None:
        return None
    last, prev = bars[-1], bars[-2]
    gain = 100.0 * (last.close / prev.close - 1.0) if prev.close else 0.0
    in_range = flags.close_in_range(last)
    fired = (rvol >= IGNITION_VOLUME
             and in_range >= IGNITION_CLOSE_IN_RANGE
             and gain >= IGNITION_GAIN_PCT)
    return {
        "fired": fired,
        "rvol": round(rvol, 2),
        "close_in_range": round(in_range, 2),
        "gain_pct": round(gain, 2),
        "date": last.date.isoformat(),
    }


def _prior_breakout(bars: list[Bar], structures: list[bases.Structure],
                    current_breakout_idx: int | None, year: int,
                    ma50: list[float | None]) -> dict | None:
    """An earlier breakout in this calendar year, and how it turned out."""
    candidates = [s for s in structures
                  if s.breakout_idx is not None
                  and bars[s.breakout_idx].date.year == year
                  and (current_breakout_idx is None or s.breakout_idx < current_breakout_idx)]
    if not candidates:
        return None
    s = candidates[-1]
    idx = s.breakout_idx
    entry = bars[idx].close
    exit_idx = len(bars) - 1
    reason = "still open"
    for i in range(idx + 1, len(bars)):
        line = ma50[i]
        if entry and bars[i].close <= entry * (1.0 - stages.STOP_PCT / 100.0):
            exit_idx, reason = i, "stopped out"
            break
        if line and bars[i].close < line:
            exit_idx, reason = i, "trailed out"
            break
    outcome = 100.0 * (bars[exit_idx].close / entry - 1.0) if entry else 0.0
    return {
        "date": bars[idx].date.isoformat(),
        "month": bars[idx].date.strftime("%b"),
        "outcome_pct": round(outcome, 2),
        "reason": reason,
    }


# ---------------------------------------------------------------- the core

def _build(series: Series, params: Params, structure: bases.Structure,
           stage: stages.StageResult) -> Setup:
    bars = series.bars
    closes = [b.close for b in bars]
    ma50 = sma(closes, 50)
    alignment = trend.alignment(closes)
    last = bars[-1]
    pivot = structure.pivot
    tight, dry = _half_ratios(bars, structure.start_idx, structure.end_idx)

    year_bars = bars[-252:]
    high_52w = max(b.high for b in year_bars)
    # The stock's own base history, which is context on any card and is not a
    # property of the screen that found it. Read with defaults rather than as
    # attributes: the shape screens have no base dials, deliberately — a wedge
    # has no ceiling, and offering "how far back to look for the ceiling" on
    # one would be a control that changes nothing.
    structures = bases.history(bars, int(params.get("base_lookback_weeks", 26)) * 5,
                               float(params.get("swing_threshold_pct", 3.0)),
                               min_base_sessions=int(params.get("min_base_weeks", 3)) * 5)

    setup = Setup(
        symbol=series.symbol,
        name=series.name,
        screen=params.screen,
        stage=stage.stage,
        pivot=round(pivot, 2),
        close=round(last.close, 2),
        bases=[c.to_json() for c in structure.contractions],
        rs_rating=series.rs_rating,
        now_vs_pivot_pct=round(100.0 * (last.close / pivot - 1.0), 2) if pivot else None,
        tightening_atr_ratio=round(tight, 2) if tight else None,
        volume_dryup_ratio=round(dry, 2) if dry else None,
        up_down_volume_net=round(_up_down_volume_net(bars) or 0.0, 2),
        from_52w_high_pct=round(100.0 * (high_52w - last.close) / high_52w, 2)
        if high_52w else None,
        price_vs_50ma_pct=round(100.0 * (last.close / ma50[-1] - 1.0), 2) if ma50[-1] else None,
        base_weeks=round(structure.weeks, 1),
        base_depth_pct=round(structure.depth_pct, 2),
        flags=flags.detect(bars, pivot) + _cooling_flag(alignment, stage.stage),
        breakout_date=stage.breakout_date.isoformat() if stage.breakout_date else None,
        sessions_since_breakout=stage.sessions_since,
        base_history=[s.to_json(bars) for s in structures],
        prior_breakout=_prior_breakout(bars, structures, structure.breakout_idx,
                                       last.date.year, ma50),
        volume=last.volume,
        ohlc={"date": last.date.isoformat(), "open": last.open, "high": last.high,
              "low": last.low, "close": last.close,
              "change_pct": round(100.0 * (last.close / bars[-2].close - 1.0), 2)
              if len(bars) > 1 and bars[-2].close else None},
    )
    setup.trend = alignment.to_json() if alignment else None
    spark = ignition(bars)
    setup.ignition = spark
    setup.rvol = spark["rvol"] if spark else None
    setup.criteria = criteria(setup, alignment)
    if structure.breakout_idx is not None:
        setup.breakout_metrics = _breakout_metrics(bars, structure.breakout_idx, ma50)
    return setup


def _cooling_flag(alignment, stage_name: str) -> list[str]:
    """Cooling only means something once the thing has actually moved.

    On a setup still forming, the short averages crossing is just what a base
    does while it rests — printing a caution there would need a caveat to
    explain it away, which is the same as it not being worth printing.
    """
    if alignment is None or not alignment.cooling:
        return []
    if stage_name not in (stages.FRESH, stages.CLIMBING):
        return []
    return ["cooling"]


def _gate_rs(series: Series, params: Params) -> bool:
    """IPO base has no RS dial at all. That is deliberate — do not add one."""
    if not params.has("min_rs"):
        return True
    rating = series.rs_rating
    return isinstance(rating, int) and rating >= int(params.min_rs)


def _structural_gates(structure: bases.Structure, params: Params) -> bool:
    if structure.weeks < float(params.min_base_weeks):
        return False
    if structure.depth_pct > float(params.max_base_depth_pct):
        return False
    return True


def _detect(series: Series, params: Params, extra_now: list = (),
            extra_always: list = ()) -> Setup | None:
    """Shared spine. extra_now gates apply to live setups, extra_always to all.

    A name that already broke out is not asked to prove it is still near its
    pivot or still a leader — it is on the screen so its outcome can be shown.
    """
    bars = series.bars
    if len(bars) < 30:
        return None
    closes = [b.close for b in bars]
    ma50 = sma(closes, 50)

    structure = bases.find(bars, int(params.base_lookback_weeks) * 5,
                           float(params.swing_threshold_pct),
                           min_base_sessions=int(params.min_base_weeks) * 5)
    if structure is None or not _structural_gates(structure, params):
        return None
    if any(not check(series, params, structure) for check in extra_always):
        return None

    stage = stages.classify(bars, ma50, structure.breakout_idx,
                            int(params.fresh_breakout_sessions), bars[-1].date.year)
    if stage is None:
        return None

    live = stage.stage in (stages.FORMING, stages.FRESH)
    if stage.stage != stages.PLAYED_OUT and not _gate_rs(series, params):
        return None
    if live:
        if any(not check(series, params, structure) for check in extra_now):
            return None
        near = 100.0 * (bars[-1].close / structure.pivot - 1.0)
        if near < -float(params.max_from_pivot_pct):
            return None
    return _build(series, params, structure, stage)


# ---------------------------------------------------------------- screens

def _above_ma(window: int):
    def check(series: Series, params: Params, structure: bases.Structure) -> bool:
        key = f"require_above_{window}ma"
        if not params.get(key, False):
            return True
        line = sma([b.close for b in series.bars], window)[-1]
        return bool(line and series.bars[-1].close > line)
    return check


def _near_52w_high(series: Series, params: Params, structure: bases.Structure) -> bool:
    limit = params.get("max_from_52w_high_pct")
    if limit is None:
        return True
    year_bars = series.bars[-252:]
    high = max(b.high for b in year_bars)
    if not high:
        return False
    return 100.0 * (high - series.bars[-1].close) / high <= float(limit)


def _all_time_high_pivot(series: Series, params: Params, structure: bases.Structure) -> bool:
    """Nothing had ever traded above the pivot when the base finished.

    Measured up to the end of the base, not to today: once a name breaks out it
    sets a new high, and judging it against that would throw away every blue-sky
    breakout the moment it happened.
    """
    tolerance = float(params.get("all_time_high_tolerance_pct", 2.0)) / 100.0
    all_time = max(b.high for b in series.bars[:structure.end_idx + 1])
    return structure.pivot >= all_time * (1.0 - tolerance)


def _recently_listed(series: Series, params: Params, structure: bases.Structure) -> bool:
    first = series.list_date or series.bars[0].date
    weeks = (series.bars[-1].date - first).days / 7.0
    return weeks <= float(params.max_weeks_listed)


def _tightening(series: Series, params: Params, structure: bases.Structure) -> bool:
    tight, dry = _half_ratios(series.bars, structure.start_idx, structure.end_idx)
    if tight is None or dry is None:
        return False
    # Params are stated as "second half no more than N× the first half"; the
    # ratios above are reported the other way up so the card reads larger = calmer.
    return (1.0 / tight <= float(params.max_second_half_atr_ratio)
            and 1.0 / dry <= float(params.max_second_half_volume_ratio))


def _flat(series: Series, params: Params, structure: bases.Structure) -> bool:
    """A flat base is a shallow, level shelf — not merely a short one.

    Two things separate it from any other pause. It is shallow, which the depth
    parameter already covers. And it is *level*: a base that drifts steadily
    downward through its own span is a decline, not a shelf, however shallow.
    So the second half's lows must not sit materially below the first half's.
    """
    bars = series.bars
    start, end = structure.start_idx, structure.end_idx
    span = end - start + 1
    if span < 10:
        return False
    mid = start + span // 2
    first_low = min(b.low for b in bars[start:mid])
    second_low = min(b.low for b in bars[mid:end + 1])
    if first_low <= 0:
        return False
    drift_pct = 100.0 * (first_low - second_low) / first_low
    return drift_pct <= float(params.max_downward_drift_pct)


def _cup_and_handle(series: Series, params: Params,
                    structure: bases.Structure) -> bool:
    """A rounded bottom with a small pause below the lid, in that order.

    Four things have to be true. Each rules out a shape that would otherwise
    pass, and three of them were added because a shape did pass:

    1. The low sits in the middle of the base. A low at the left edge is a
       recovery; a low at the right edge is still a fall.
    2. It is *round*, not a V. A V also has its low in the middle — that check
       alone let a sharp fall and an equally sharp bounce through. What tells
       them apart is time spent near the bottom: a cup lingers there, a V passes
       through it in a few sessions.
    3. Both rims come back to a similar height, or the stock is still climbing
       back to where it was rather than rounding out.
    4. The handle is short, shallow and high in the cup. Its length is measured
       from where it actually began — the last touch of the right rim — because
       looking at a fixed window at the end made a three-month slide look like a
       three-week pause.
    """
    bars = series.bars
    start, end = structure.start_idx, structure.end_idx
    span = end - start + 1
    if span < 25:
        return False
    segment = bars[start:end + 1]
    lows = [b.low for b in segment]
    highs = [b.high for b in segment]
    depth = structure.pivot - structure.low
    if depth <= 0:
        return False

    # 1. The low belongs in the middle.
    low_idx = lows.index(min(lows))
    if not (0.25 <= low_idx / max(1, span - 1) <= 0.75):
        return False

    # 2. Round, not V. How many sessions were spent in the bottom of the range?
    floor = structure.low + depth * 0.4
    time_low = sum(1 for b in segment if b.close <= floor) / span
    if time_low < float(params.min_time_at_lows):
        return False

    # 3. Both rims within reach of the lid.
    edge = max(2, span // 10)
    tolerance = 1 - float(params.max_rim_gap_pct) / 100.0
    if max(highs[:edge]) < structure.pivot * tolerance:
        return False
    if max(highs[-edge:]) < structure.pivot * tolerance:
        return False

    # 4. The handle, measured from where it started rather than a fixed window.
    after_low = highs[low_idx:]
    rim_idx = low_idx + after_low.index(max(after_low))
    handle = segment[rim_idx:]
    if len(handle) < 3:
        return False
    if len(handle) > int(params.max_handle_weeks) * 5:
        return False
    handle_high = max(b.high for b in handle)
    handle_low = min(b.low for b in handle)
    if handle_high <= 0:
        return False
    if 100.0 * (handle_high - handle_low) / handle_high > float(params.max_handle_depth_pct):
        return False
    # Its low must sit high in the cup, not back down at the bottom.
    return (handle_low - structure.low) / depth >= float(params.min_handle_position)


def detect_flat_base(series: Series, params: Params) -> Setup | None:
    return _detect(series, params,
                   extra_now=[_trend_rungs, _above_ma(50), _near_52w_high],
                   extra_always=[_flat])


def detect_cup_and_handle(series: Series, params: Params) -> Setup | None:
    return _detect(series, params,
                   extra_now=[_trend_rungs, _above_ma(50)],
                   extra_always=[_cup_and_handle])


def _trend_rungs(series: Series, params: Params,
                 structure: bases.Structure) -> bool:
    """The moving-average dial. Zero admits everything, which is the default.

    A stock without 200 sessions has no 200-day average, so there is no answer
    to give. It passes rather than failing, because the dial asks whether the
    averages disagree — not whether we have enough history to ask.
    """
    wanted = int(params.get("min_trend_rungs", 0) or 0)
    if wanted <= 0:
        return True
    alignment = trend.alignment([b.close for b in series.bars])
    if alignment is None:
        return True
    return alignment.rungs >= wanted


def detect_vcp(series: Series, params: Params) -> Setup | None:
    return _detect(series, params,
                   extra_now=[_trend_rungs, _above_ma(50), _above_ma(200), _near_52w_high],
                   extra_always=[_tightening])


def detect_blue_sky(series: Series, params: Params) -> Setup | None:
    return _detect(series, params,
                   extra_now=[_trend_rungs], extra_always=[_all_time_high_pivot])


def detect_multi_year(series: Series, params: Params) -> Setup | None:
    return _detect(series, params, extra_now=[_trend_rungs, _above_ma(200)])


def detect_ipo(series: Series, params: Params) -> Setup | None:
    return _detect(series, params, extra_now=[_trend_rungs, _above_ma(50)],
                   extra_always=[_recently_listed])


# ---------------------------------------------------------------- shapes
#
# Wedges, triangles, flags and squeezes do not come from bases.find, so they
# need their own way in. Everything after the structure is shared: the Shape is
# adapted into a bases.Structure and handed to the same _build, so a shape setup
# carries the same fields, renders in the same card and diffs the same way.


def _structure_from_shape(shape, bars: list[Bar]) -> bases.Structure:
    window = bars[shape.start_idx:shape.end_idx + 1]
    return bases.Structure(
        start_idx=shape.start_idx,
        end_idx=shape.end_idx,
        pivot=shape.level,
        depth_pct=shape.depth_pct,
        weeks=shape.weeks,
        low=min(b.low for b in window) if window else shape.level,
        contractions=[],
        breakout_idx=None,
    )


def _first_cross(bars: list[Bar], after_idx: int, level: float,
                 direction: str) -> int | None:
    """The first close beyond the level after the shape ended.

    Beyond means above for a shape read upward and below for one read downward,
    which is the single place the direction of a shape becomes an index rather
    than a label.
    """
    for i in range(after_idx + 1, len(bars)):
        if direction == stages.SHORT:
            if bars[i].close < level:
                return i
        elif bars[i].close > level:
            return i
    return None


def _detect_shape(series: Series, params: Params, kinds: set[str],
                  direction: str, finder) -> Setup | None:
    """One shape screen.

    The fit is tried at several end points, not just today. A wedge that broke
    three sessions ago is no longer a wedge if you fit through those three
    sessions — the breakout drags the upper line up and the convergence test
    fails — so a screen that only ever fitted to the last bar would show
    nothing but "forming" and would never report the resolution it exists to
    catch. So: fit to today first, and if that finds a shape with price still
    inside it, that is a forming setup. Otherwise step the end back one session
    at a time and take the first shape whose level has since been crossed.
    """
    bars = series.bars
    if len(bars) < 60:
        return None
    closes = [b.close for b in bars]
    ma50 = sma(closes, 50)
    fresh = int(params.fresh_breakout_sessions)

    chosen = None
    breakout_idx = None
    for lag in range(0, fresh + 1):
        sub = bars if lag == 0 else bars[:len(bars) - lag]
        if len(sub) < 60:
            break
        shape = finder(sub, params)
        if shape is None or shape.kind not in kinds:
            continue
        cross = _first_cross(bars, shape.end_idx, shape.level, direction)
        if lag == 0 and cross is None:
            chosen, breakout_idx = shape, None
            break
        if cross is not None:
            chosen, breakout_idx = shape, cross
            break

    if chosen is None:
        return None

    structure = _structure_from_shape(chosen, bars)
    structure.breakout_idx = breakout_idx
    stage = stages.classify(bars, ma50, breakout_idx, fresh,
                            bars[-1].date.year, direction)
    if stage is None:
        return None
    if stage.stage != stages.PLAYED_OUT and not _gate_rs(series, params):
        return None

    setup = _build(series, params, structure, stage)
    setup.direction = direction
    setup.shape = chosen.to_json(bars)
    setup.shape["volume_vs_prior"] = _round_or_none(
        shapemod.volume_trend(bars, chosen.start_idx))
    setup.shape["atr_vs_prior"] = _round_or_none(
        shapemod.atr_compression(bars, chosen.start_idx))
    return setup


def _round_or_none(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _shape_screen(kinds: set[str], direction: str, finder):
    def detect(series: Series, params: Params) -> Setup | None:
        return _detect_shape(series, params, kinds, direction, finder)
    return detect


def _converging(sub, params):
    ratio = params.get("max_volume_ratio")
    return shapemod.find_converging(
        sub,
        lookback=int(params.get("shape_lookback_weeks", 12)) * 5,
        threshold_pct=float(params.get("swing_threshold_pct", 3.0)),
        min_sessions=int(params.get("min_shape_weeks", 2)) * 5,
        max_convergence=float(params.get("max_convergence", 0.70)),
        max_volume_ratio=float(ratio) if ratio else None,
    )


def _squeeze(sub, params):
    return shapemod.find_squeeze(
        sub,
        min_sessions=int(params.get("min_squeeze_sessions", 5)),
        window=int(params.get("squeeze_window", 20)),
        keltner_multiple=float(params.get("keltner_multiple", 1.5)),
    )


DETECTORS = {
    "vcp": detect_vcp,
    "blue_sky": detect_blue_sky,
    "multi_year": detect_multi_year,
    "ipo": detect_ipo,
    "flat_base": detect_flat_base,
    "cup_and_handle": detect_cup_and_handle,
    # Shape screens. Each is direction-coherent on purpose: a screen mixing a
    # rising wedge with a falling one would have half its "fresh" column
    # meaning a breakout and half meaning a breakdown, and the stage counts
    # would be the sum of two different things.
    "falling_wedge": _shape_screen({shapemod.FALLING_WEDGE}, stages.LONG, _converging),
    "rising_wedge": _shape_screen({shapemod.RISING_WEDGE}, stages.SHORT, _converging),
    "triangle": _shape_screen({shapemod.SYMMETRICAL, shapemod.ASCENDING},
                              stages.LONG, _converging),
    "descending_triangle": _shape_screen({shapemod.DESCENDING}, stages.SHORT,
                                         _converging),
    "squeeze": _shape_screen({shapemod.SQUEEZE}, stages.LONG, _squeeze),
}

#: Which way each screen reads its level. Anything that counts breakouts across
#: the whole site must consult this: a bear flag in its "fresh" bucket has
#: broken DOWN, and adding it to a breakout tally would report a falling stock
#: as one that cleared a pivot.
SCREEN_DIRECTION = {
    "vcp": stages.LONG,
    "blue_sky": stages.LONG,
    "multi_year": stages.LONG,
    "ipo": stages.LONG,
    "flat_base": stages.LONG,
    "cup_and_handle": stages.LONG,
    "falling_wedge": stages.LONG,
    "rising_wedge": stages.SHORT,
    "triangle": stages.LONG,
    "descending_triangle": stages.SHORT,
    "squeeze": stages.LONG,
}


def direction_of(screen: str) -> str:
    return SCREEN_DIRECTION.get(screen, stages.LONG)
