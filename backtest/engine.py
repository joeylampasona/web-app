"""Rule replay. One pass over the calendar, one decision a day."""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field

from backtest.settings import BacktestSettings
from data import settings as cfg
from data.market import Market
from data.types import Bar
from patterns import bases
from patterns.indicators import atr_pct, mean, sma
from patterns.params import Params
from rankings import rs

TRAIL_WINDOWS = {"trail_50d": 50, "trail_30w": 150}
EARNINGS_CADENCE_DAYS = 91


@dataclass
class Candidate:
    symbol: str
    idx: int
    date: dt.date
    pivot: float
    breakout_close: float
    rs_rating: int | None


@dataclass
class Trade:
    ticker: str
    entry_date: dt.date
    entry_price: float
    exit_date: dt.date
    exit_price: float
    shares: float
    return_pct: float
    gross_return_pct: float
    r_multiple: float
    exit_reason: str
    pnl: float

    def to_json(self) -> dict:
        out = asdict(self)
        out["entry_date"] = self.entry_date.isoformat()
        out["exit_date"] = self.exit_date.isoformat()
        for key in ("entry_price", "exit_price", "return_pct", "gross_return_pct",
                    "r_multiple", "pnl"):
            out[key] = round(out[key], 4 if key == "r_multiple" else 2)
        out["shares"] = round(self.shares, 4)
        return out


@dataclass
class Position:
    symbol: str
    entry_idx: int
    entry_date: dt.date
    entry_price: float
    shares: float
    stop_price: float


@dataclass
class RunOutput:
    settings: BacktestSettings
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[dt.date, float]] = field(default_factory=list)
    passed_up: int = 0
    strong_sessions: int = 0
    total_sessions: int = 0
    benchmark_return_pct: float | None = None
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- candidates

class _Symbol:
    """Precomputed arrays for one symbol, so the day loop stays cheap."""

    def __init__(self, symbol: str, bars: list[Bar]) -> None:
        self.symbol = symbol
        self.bars = bars
        self.closes = [b.close for b in bars]
        self.sma50 = sma(self.closes, 50)
        self.sma150 = sma(self.closes, 150)
        self.sma200 = sma(self.closes, 200)
        self.index = {b.date: i for i, b in enumerate(bars)}


def rs_timeline(market: Market, step: int = 5) -> list[tuple[dt.date, dict[str, int]]]:
    """RS ratings sampled through history, so entries are gated point-in-time."""
    calendar = market.calendar
    out: list[tuple[dt.date, dict[str, int]]] = []
    for offset in range(0, max(1, len(calendar) - 260), step):
        day = calendar[-1 - offset]
        out.append((day, rs.numeric(rs.ratings(market, offset))))
    out.reverse()
    return out


def _rating_at(timeline, day: dt.date, symbol: str) -> int | None:
    chosen = None
    for stamp, table in timeline:
        if stamp > day:
            break
        chosen = table
    return chosen.get(symbol) if chosen else None


def candidates(market: Market, params: Params, timeline) -> dict[str, list[Candidate]]:
    """Every historical breakout that passed this screen's gates on its own day."""
    out: dict[str, list[Candidate]] = {}
    lookback = int(params.base_lookback_weeks) * 5
    min_sessions = int(params.min_base_weeks) * 5
    for symbol in market.universe:
        bars = market.series.get(symbol) or []
        if len(bars) < 120:
            continue
        panel = _Symbol(symbol, bars)
        found: list[Candidate] = []
        for structure in bases.history(bars, lookback, float(params.swing_threshold_pct),
                                       limit=40, min_base_sessions=min_sessions):
            idx = structure.breakout_idx
            if idx is None or idx >= len(bars) - 1:
                continue
            if structure.weeks < float(params.min_base_weeks):
                continue
            if structure.depth_pct > float(params.max_base_depth_pct):
                continue
            if not _screen_gates(market, symbol, panel, structure, idx, params, timeline):
                continue
            rating = _rating_at(timeline, bars[idx].date, symbol)
            found.append(Candidate(symbol, idx, bars[idx].date, structure.pivot,
                                   bars[idx].close, rating))
        if found:
            out[symbol] = found
    return out


def _screen_gates(market: Market, symbol: str, panel: _Symbol,
                  structure: bases.Structure, idx: int, params: Params, timeline) -> bool:
    bars = panel.bars
    close = bars[idx].close

    if params.has("min_rs"):
        rating = _rating_at(timeline, bars[idx].date, symbol)
        if rating is None or rating < int(params.min_rs):
            return False
    if params.get("require_above_50ma", False):
        line = panel.sma50[idx]
        if not line or close <= line:
            return False
    if params.get("require_above_200ma", False):
        line = panel.sma200[idx]
        if not line or close <= line:
            return False
    limit = params.get("max_from_52w_high_pct")
    if limit is not None:
        window = bars[max(0, idx - 252):idx + 1]
        high = max(b.high for b in window)
        if high and 100.0 * (high - close) / high > float(limit):
            return False
    if params.has("all_time_high_tolerance_pct"):
        tolerance = float(params.all_time_high_tolerance_pct) / 100.0
        if structure.pivot < max(b.high for b in bars[:structure.end_idx + 1]) * (1 - tolerance):
            return False
    if params.has("max_weeks_listed"):
        ref = market.refs.get(symbol)
        first = (ref.list_date if ref and ref.list_date else bars[0].date)
        if (bars[idx].date - first).days / 7.0 > float(params.max_weeks_listed):
            return False
    if params.has("max_second_half_atr_ratio"):
        start, end = structure.start_idx, structure.end_idx
        span = end - start + 1
        if span < 10:
            return False
        mid = start + span // 2
        ranges = atr_pct(bars, 5)
        first_atr = [r for r in ranges[start:mid] if r is not None]
        second_atr = [r for r in ranges[mid:end + 1] if r is not None]
        first_vol = [b.volume for b in bars[start:mid]]
        second_vol = [b.volume for b in bars[mid:end + 1]]
        if not (first_atr and second_atr and first_vol and second_vol):
            return False
        if mean(first_atr) <= 0 or mean(first_vol) <= 0:
            return False
        if mean(second_atr) / mean(first_atr) > float(params.max_second_half_atr_ratio):
            return False
        if mean(second_vol) / mean(first_vol) > float(params.max_second_half_volume_ratio):
            return False
    return True


# ---------------------------------------------------------------- the replay

def _earnings_window(market: Market, symbol: str, day: dt.date,
                     next_known: dict[str, dt.date], days: int = 7) -> bool:
    """Was the stock inside `days` of a reporting date?

    We only hold forward earnings dates, so historical ones are projected back on
    a quarterly cadence from the next known date. It is an approximation, and any
    run that uses it is flagged provisional for that reason.
    """
    known = next_known.get(symbol)
    if known is None:
        return False
    delta = (known - day).days
    into_cycle = delta % EARNINGS_CADENCE_DAYS
    return 0 <= into_cycle <= days


def run(market: Market, config: BacktestSettings,
        next_earnings: dict[str, dt.date] | None = None,
        timeline=None) -> RunOutput:
    params = Params(config.screen)
    timeline = timeline if timeline is not None else rs_timeline(market)
    pool = candidates(market, params, timeline)
    panels = {s: _Symbol(s, market.series[s]) for s in pool}

    by_date: dict[dt.date, list[Candidate]] = {}
    for rows in pool.values():
        for c in rows:
            by_date.setdefault(c.date, []).append(c)

    bench = market.bench_bars()
    bench_index = {b.date: i for i, b in enumerate(bench)}
    bench_sma200 = sma([b.close for b in bench], 200)

    calendar = [d for d in market.calendar]
    if config.period != "all":
        year = int(config.period)
        calendar = [d for d in calendar if d.year == year]
    if not calendar:
        return RunOutput(settings=config, notes=["no sessions in the selected period"])

    cost = float(cfg.get("backtest.cost_bps_round_trip", 10)) / 10_000.0
    out = RunOutput(settings=config)
    cash = float(config.starting_capital)
    open_positions: list[Position] = []
    next_earnings = next_earnings or {}

    for day in calendar:
        # -- mark to market and handle exits -------------------------------
        still_open: list[Position] = []
        for pos in open_positions:
            panel = panels[pos.symbol]
            i = panel.index.get(day)
            if i is None:
                still_open.append(pos)
                continue
            close = panel.closes[i]
            reason = ""
            if close <= pos.stop_price:
                reason = "stopped out"
            elif config.exit_rule == "take_25" and close >= pos.entry_price * 1.25:
                reason = "reached +25%"
            elif config.exit_rule in TRAIL_WINDOWS:
                line = (panel.sma50 if config.exit_rule == "trail_50d"
                        else panel.sma150)[i]
                if line and close < line:
                    reason = ("trailed out, 50-day" if config.exit_rule == "trail_50d"
                              else "trailed out, 30-week")
            if not reason:
                still_open.append(pos)
                continue
            gross = close / pos.entry_price - 1.0
            net = gross - cost
            proceeds = pos.shares * close * (1.0 - cost / 2.0)
            cash += proceeds
            risk_per_share = pos.entry_price - pos.stop_price
            out.trades.append(Trade(
                ticker=pos.symbol, entry_date=pos.entry_date, entry_price=pos.entry_price,
                exit_date=day, exit_price=close, shares=pos.shares,
                return_pct=100.0 * net, gross_return_pct=100.0 * gross,
                r_multiple=((close - pos.entry_price) / risk_per_share)
                if risk_per_share > 0 else 0.0,
                exit_reason=reason,
                pnl=pos.shares * (close - pos.entry_price) - pos.shares * pos.entry_price * cost,
            ))
        open_positions = still_open

        # -- regime --------------------------------------------------------
        bi = bench_index.get(day)
        strong = bool(bi is not None and bench_sma200[bi]
                      and bench[bi].close > bench_sma200[bi])
        out.total_sessions += 1
        out.strong_sessions += int(strong)

        # -- entries -------------------------------------------------------
        todays = sorted(by_date.get(day, []), key=lambda c: -(c.rs_rating or 0))
        for candidate in todays:
            if config.skip_weak_markets and not strong:
                continue
            if config.skip_earnings_7d and _earnings_window(market, candidate.symbol,
                                                            day, next_earnings):
                continue
            if any(p.symbol == candidate.symbol for p in open_positions):
                continue
            if len(open_positions) >= int(config.positions):
                out.passed_up += 1
                continue
            equity = cash + sum(
                p.shares * panels[p.symbol].closes[panels[p.symbol].index[day]]
                for p in open_positions if day in panels[p.symbol].index)
            price = (candidate.breakout_close if config.enter == "breakout_close"
                     else candidate.pivot)
            if price <= 0:
                continue
            target_value = min(config.position_size(equity), cash)
            shares = target_value / price
            if shares <= 0:
                continue
            cash -= shares * price * (1.0 + cost / 2.0)
            open_positions.append(Position(
                symbol=candidate.symbol, entry_idx=candidate.idx, entry_date=day,
                entry_price=price, shares=shares,
                stop_price=price * (1.0 - float(config.stop_pct) / 100.0)))

        equity = cash
        for p in open_positions:
            panel = panels[p.symbol]
            i = panel.index.get(day)
            if i is not None:
                equity += p.shares * panel.closes[i]
            else:
                equity += p.shares * p.entry_price
        out.equity_curve.append((day, equity))

    # -- close anything still open at the end -----------------------------
    last = calendar[-1]
    for pos in open_positions:
        panel = panels[pos.symbol]
        i = panel.index.get(last, len(panel.closes) - 1)
        close = panel.closes[i]
        gross = close / pos.entry_price - 1.0
        risk_per_share = pos.entry_price - pos.stop_price
        out.trades.append(Trade(
            ticker=pos.symbol, entry_date=pos.entry_date, entry_price=pos.entry_price,
            exit_date=last, exit_price=close, shares=pos.shares,
            return_pct=100.0 * (gross - cost), gross_return_pct=100.0 * gross,
            r_multiple=((close - pos.entry_price) / risk_per_share)
            if risk_per_share > 0 else 0.0,
            exit_reason="still open at the end of the period",
            pnl=pos.shares * (close - pos.entry_price)))

    first_bench = next((b for b in bench if b.date >= calendar[0]), None)
    last_bench = next((b for b in reversed(bench) if b.date <= calendar[-1]), None)
    if first_bench and last_bench and first_bench.close:
        out.benchmark_return_pct = 100.0 * (last_bench.close / first_bench.close - 1.0)

    if config.skip_earnings_7d:
        out.notes.append(
            "Historical earnings dates are projected backwards on a quarterly cadence "
            "from the next known date. The earnings filter is therefore approximate.")
    return out
