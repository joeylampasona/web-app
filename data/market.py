"""One load of everything the analytic layers need, shared between stages."""
from __future__ import annotations

import datetime as dt
import functools
import sqlite3
from dataclasses import dataclass, field

from data import settings, store
from data.types import Bar, TickerRef
from patterns import indicators


@dataclass
class Market:
    as_of: dt.date
    calendar: list[dt.date]
    universe: list[str]
    series: dict[str, list[Bar]]
    refs: dict[str, TickerRef]
    caps: dict[str, float] = field(default_factory=dict)
    industries: dict[str, str] = field(default_factory=dict)
    themes: dict[str, list[str]] = field(default_factory=dict)
    benchmark: str = "SPY"

    # ---- cached per-symbol derivations -------------------------------

    @functools.lru_cache(maxsize=None)
    def closes(self, symbol: str) -> tuple[float, ...]:
        return tuple(b.close for b in self.series.get(symbol, []))

    @functools.lru_cache(maxsize=None)
    def sma(self, symbol: str, window: int) -> tuple[float | None, ...]:
        return tuple(indicators.sma(self.closes(symbol), window))

    def bench_bars(self) -> list[Bar]:
        return self.series.get(self.benchmark, [])

    def last_close(self, symbol: str) -> float | None:
        c = self.closes(symbol)
        return c[-1] if c else None

    def __hash__(self) -> int:          # lru_cache on methods needs this
        return id(self)


def load(conn: sqlite3.Connection | None = None, include_all: bool = False) -> Market:
    """Universe survivors plus the benchmark and sector ETFs.

    include_all pulls every symbol with bars, which the backtest needs so a
    name that has since left the universe still has history to replay.
    """
    conn = conn or store.open_db()
    as_of = store.last_session(conn)
    if as_of is None:
        raise RuntimeError("no bars in the database — run `python -m cli universe --refresh`")

    benchmark = settings.get("universe.benchmark", "SPY")
    etfs = list(settings.get("rankings.sector_etfs", []))
    # Broad-market symbols for the home page. Their bars are already in the
    # database -- the grouped-daily call stores the whole market, unfiltered --
    # they were simply never loaded, because loading is scoped to the universe
    # plus the benchmark and the sector ETFs.
    indexes = list(settings.get("rankings.indexes", []))
    universe = store.universe_symbols(conn)
    wanted = list(dict.fromkeys(
        (store.all_symbols_with_bars(conn) if include_all else universe)
        + [benchmark] + etfs + indexes))

    series = store.load_many(conn, wanted)
    refs: dict[str, TickerRef] = {}
    for sym in wanted:
        ref = store.get_ticker(conn, sym)
        if ref:
            refs[sym] = ref

    caps, industries = {}, {}
    for row in store.universe_rows(conn):
        caps[row["symbol"]] = row["market_cap"] or 0.0
        industries[row["symbol"]] = row["industry"] or "Unclassified"

    return Market(
        as_of=as_of,
        calendar=store.trading_dates(conn),
        universe=universe,
        series=series,
        refs=refs,
        caps=caps,
        industries=industries,
        themes=store.themes_for(conn),
        benchmark=benchmark,
    )
