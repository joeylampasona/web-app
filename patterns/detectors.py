"""Four detectors. Each is a pure function of (series, params) and returns a
structured result or None. Every threshold comes from the params object.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any

from data.types import Bar
from patterns import bases, flags, stages
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
    last = bars[-1]
    pivot = structure.pivot
    tight, dry = _half_ratios(bars, structure.start_idx, structure.end_idx)

    year_bars = bars[-252:]
    high_52w = max(b.high for b in year_bars)
    structures = bases.history(bars, int(params.base_lookback_weeks) * 5,
                               float(params.swing_threshold_pct),
                               min_base_sessions=int(params.min_base_weeks) * 5)

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
        flags=flags.detect(bars, pivot),
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
    if structure.breakout_idx is not None:
        setup.breakout_metrics = _breakout_metrics(bars, structure.breakout_idx, ma50)
    return setup


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


def detect_vcp(series: Series, params: Params) -> Setup | None:
    return _detect(series, params,
                   extra_now=[_above_ma(50), _above_ma(200), _near_52w_high],
                   extra_always=[_tightening])


def detect_blue_sky(series: Series, params: Params) -> Setup | None:
    return _detect(series, params, extra_always=[_all_time_high_pivot])


def detect_multi_year(series: Series, params: Params) -> Setup | None:
    return _detect(series, params, extra_now=[_above_ma(200)])


def detect_ipo(series: Series, params: Params) -> Setup | None:
    return _detect(series, params, extra_now=[_above_ma(50)],
                   extra_always=[_recently_listed])


DETECTORS = {
    "vcp": detect_vcp,
    "blue_sky": detect_blue_sky,
    "multi_year": detect_multi_year,
    "ipo": detect_ipo,
}
