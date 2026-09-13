"""RS rating — a 3/6/12-month composite against the benchmark, ranked 1-99."""
from __future__ import annotations

from data import settings
from data.market import Market
from data.types import Bar
from patterns.indicators import percentile_ranks

NOT_RANKED = "not ranked yet"

Rating = int | str


def _return_over(bars: list[Bar], window: int, offset: int = 0) -> float | None:
    end = len(bars) - 1 - offset
    start = end - window
    if start < 0 or end < 0 or bars[start].close <= 0:
        return None
    return bars[end].close / bars[start].close - 1.0


def raw_scores(market: Market, offset: int = 0) -> dict[str, float]:
    """Weighted sum of excess returns vs the benchmark. Unranked names absent."""
    cfg = settings.get("rankings", {}) or {}
    windows: dict[str, int] = cfg.get("rs_windows", {"m3": 63, "m6": 126, "m12": 252})
    weights: dict[str, float] = cfg.get("rs_weights", {"m3": 0.4, "m6": 0.3, "m12": 0.3})
    min_history = int(cfg.get("rs_min_history", 200))

    bench = market.bench_bars()
    bench_returns = {k: _return_over(bench, w, offset) for k, w in windows.items()}

    scores: dict[str, float] = {}
    for symbol in market.universe:
        bars = market.series.get(symbol) or []
        if len(bars) - offset < min_history:
            continue
        total, used = 0.0, 0.0
        for key, window in windows.items():
            own = _return_over(bars, window, offset)
            base = bench_returns.get(key)
            if own is None or base is None:
                continue
            total += float(weights.get(key, 0.0)) * (own - base)
            used += float(weights.get(key, 0.0))
        if used <= 0:
            continue
        scores[symbol] = total / used
    return scores


def ratings(market: Market, offset: int = 0) -> dict[str, Rating]:
    """1-99 per symbol. Names without enough history get the literal string
    `not ranked yet`, which the UI prints verbatim rather than rendering as 0."""
    scores = raw_scores(market, offset)
    ranked = percentile_ranks(scores)
    out: dict[str, Rating] = {s: NOT_RANKED for s in market.universe}
    out.update(ranked)
    return out


def numeric(ratings_map: dict[str, Rating]) -> dict[str, int]:
    return {k: v for k, v in ratings_map.items() if isinstance(v, int)}


def etf_ratings(market: Market) -> list[dict]:
    """Sector ETFs ranked among themselves, computed separately from stocks."""
    cfg = settings.get("rankings", {}) or {}
    windows = cfg.get("rs_windows", {"m3": 63, "m6": 126, "m12": 252})
    weights = cfg.get("rs_weights", {"m3": 0.4, "m6": 0.3, "m12": 0.3})
    bench = market.bench_bars()
    bench_returns = {k: _return_over(bench, w) for k, w in windows.items()}

    scores: dict[str, float] = {}
    for symbol in settings.get("rankings.sector_etfs", []) or []:
        bars = market.series.get(symbol) or []
        if not bars:
            continue
        total, used = 0.0, 0.0
        for key, window in windows.items():
            own = _return_over(bars, window)
            base = bench_returns.get(key)
            if own is None or base is None:
                continue
            total += float(weights.get(key, 0.0)) * (own - base)
            used += float(weights.get(key, 0.0))
        if used > 0:
            scores[symbol] = total / used
    ranked = percentile_ranks(scores)
    rows = []
    for symbol, score in sorted(scores.items(), key=lambda kv: -kv[1]):
        bars = market.series.get(symbol) or []
        rows.append({
            "symbol": symbol,
            "name": market.refs[symbol].name if symbol in market.refs else symbol,
            "rs_rating": ranked.get(symbol),
            "excess_return_pct": round(100.0 * score, 2),
            "close": bars[-1].close if bars else None,
        })
    return rows


class Bundle:
    """Ratings now and at three lookbacks, so every layer sees one consistent set."""

    def __init__(self, market: Market) -> None:
        self.market = market
        self.now = ratings(market, 0)
        self.w1 = ratings(market, 5)
        self.m1 = ratings(market, int(settings.get("rankings.rotation_lookback", 21)))
        self.m3 = ratings(market, 63)

    def change(self, symbol: str, span: str = "m1") -> int | None:
        now = self.now.get(symbol)
        then = getattr(self, span).get(symbol)
        if isinstance(now, int) and isinstance(then, int):
            return now - then
        return None

    def numeric_now(self) -> dict[str, int]:
        return numeric(self.now)
