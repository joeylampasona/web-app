"""A deterministic offline fixture, not a data source.

Nothing here claims to be a real company: tickers and names are invented, so
no fabricated price series is ever published under a real company's name. The
benchmark and sector ETF symbols come from config so the rest of the pipeline
needs no special case. Everything built from this adapter is stamped
``data_source: "synthetic_demo"`` in meta.json, which the web app banners.

Series are constructed rather than simulated: a given symbol is assigned an
archetype and its path is drawn to contain the structure that archetype
implies, so the detectors have honest material to find.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import random
from collections.abc import Sequence

from data import settings
from data.adapters.base import DataAdapter
from data.types import Bar, EarningsEvent, OptionChain, OptionExpiry, TickerRef

PREFIX = ["Ald", "Bry", "Cor", "Dax", "Ely", "Fen", "Gal", "Hal", "Iri", "Jun",
          "Kel", "Lum", "Mer", "Nov", "Orb", "Pyr", "Quen", "Rho", "Sol", "Ter",
          "Umb", "Ver", "Wex", "Xan", "Yar", "Zeph"]
STEM = ["ax", "on", "ex", "ia", "or", "us", "yn", "ar", "el", "im"]
TAIL = ["Systems", "Dynamics", "Labs", "Industries", "Holdings", "Technologies",
        "Works", "Microsystems", "Networks", "Sciences", "Partners", "Group"]

INDUSTRIES = [
    "Semiconductors & Related Devices",
    "Semiconductor Equipment",
    "Computer Hardware",
    "Computer Networking",
    "Computer Storage Devices",
    "Optical Instruments & Lenses",
    "Quantum Computing Systems",
    "Data Processing & Hosting",
    "Prepackaged Software",
    "Electric Power Generation",
    "Electrical Equipment",
    "Uranium Mining",
    "Aerospace & Defense",
    "Biotechnology",
    "Pharmaceutical Preparations",
    "Medical Devices",
    "Capital Markets",
    "Commercial Banking",
    "Retail Stores",
    "Restaurants",
    "Oil & Gas Extraction",
    "Construction Machinery",
    "Trucking & Logistics",
    "Apparel",
    "Household Products",
    "Insurance Carriers",
]

# Archetype mix. Most of the market is going nowhere in particular.
ARCHETYPES = (
    ["vcp"] * 11 + ["blue_sky"] * 7 + ["multi_year"] * 6 + ["ipo"] * 6
    + ["laggard"] * 28 + ["chop"] * 42
)


def _seed_for(symbol: str, base_seed: int) -> int:
    digest = hashlib.md5(f"{base_seed}:{symbol}".encode()).hexdigest()
    return int(digest[:12], 16)


def sessions_ending(end: dt.date, count: int) -> list[dt.date]:
    """`count` weekday sessions ending on or before `end`."""
    out: list[dt.date] = []
    day = end
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day -= dt.timedelta(days=1)
    return list(reversed(out))


class SyntheticAdapter(DataAdapter):
    name = "synthetic"

    def __init__(self, end: dt.date | None = None) -> None:
        cfg = settings.get("data.synthetic", {}) or {}
        self.seed = int(cfg.get("seed", 20260912))
        self.n_symbols = int(cfg.get("symbols", 320))
        self.n_days = int(cfg.get("days", 520))
        self.end = end or self._last_weekday(dt.date.today())
        self.benchmark = settings.get("universe.benchmark", "SPY")
        self.sector_etfs = list(settings.get("rankings.sector_etfs", []))
        self.dates = sessions_ending(self.end, self.n_days)
        self._refs: list[TickerRef] | None = None
        self._series: dict[str, list[Bar]] = {}

    @staticmethod
    def _last_weekday(day: dt.date) -> dt.date:
        while day.weekday() >= 5:
            day -= dt.timedelta(days=1)
        return day

    # ------------------------------------------------------------ interface

    def get_universe(self) -> list[TickerRef]:
        if self._refs is not None:
            return self._refs
        rng = random.Random(self.seed)
        refs: list[TickerRef] = []
        seen: set[str] = set()
        while len(refs) < self.n_symbols:
            sym = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                          for _ in range(rng.choice([3, 3, 4])))
            if sym in seen or sym in self.sector_etfs or sym == self.benchmark:
                continue
            seen.add(sym)
            srng = random.Random(_seed_for(sym, self.seed))
            industry = srng.choice(INDUSTRIES)
            name = (srng.choice(PREFIX) + srng.choice(STEM)).capitalize() + " " + srng.choice(TAIL)
            archetype = srng.choice(ARCHETYPES)
            if archetype == "ipo":
                weeks_listed = srng.randint(26, 48)
                list_date = self.end - dt.timedelta(weeks=weeks_listed)
            else:
                list_date = self.end - dt.timedelta(days=srng.randint(900, 9000))
            refs.append(TickerRef(symbol=sym, name=name, type="CS",
                                  exchange=srng.choice(["XNAS", "XNYS"]),
                                  industry=industry, list_date=list_date))
        for sym in [self.benchmark] + self.sector_etfs:
            refs.append(TickerRef(symbol=sym, name=f"{sym} index proxy", type="ETF",
                                  exchange="ARCX", industry="Exchange Traded Fund",
                                  list_date=self.end - dt.timedelta(days=6000)))
        self._refs = refs
        return refs

    def get_grouped_daily(self, date: dt.date) -> list[Bar]:
        if date.weekday() >= 5 or date not in set(self.dates):
            return []
        out: list[Bar] = []
        for ref in self.get_universe():
            for bar in self.series(ref):
                if bar.date == date:
                    out.append(bar)
                    break
        return out

    def get_reference(self, symbol: str) -> TickerRef | None:
        for ref in self.get_universe():
            if ref.symbol == symbol:
                return ref
        return None

    def get_earnings_dates(self, symbols: Sequence[str]) -> dict[str, list[EarningsEvent]]:
        out: dict[str, list[EarningsEvent]] = {}
        for sym in symbols:
            rng = random.Random(_seed_for(sym, self.seed + 7))
            offset = rng.randint(2, 80)
            date = self.end + dt.timedelta(days=offset)
            confirmed = "confirmed" if offset <= 21 else ("tentative" if offset <= 55 else "window")
            events = [EarningsEvent(sym, date, confirmed)]
            events.append(EarningsEvent(sym, date + dt.timedelta(days=91), "window"))
            out[sym] = events
        return out

    def get_option_chain(self, symbol: str) -> OptionChain | None:
        rng = random.Random(_seed_for(symbol, self.seed + 13))
        if rng.random() < 0.25:
            return None                      # no listed options
        bars = self._series.get(symbol) or []
        spot = bars[-1].close if bars else 50.0
        base_iv = rng.uniform(0.28, 0.85)
        expiries: list[OptionExpiry] = []
        for weeks in (1, 2, 3, 4, 6, 9, 13):
            expiry = self.end + dt.timedelta(weeks=weeks)
            while expiry.weekday() != 4:
                expiry += dt.timedelta(days=1)
            iv = base_iv * (1.0 + rng.uniform(-0.06, 0.06)) * (1.0 - 0.012 * weeks)
            expiries.append(OptionExpiry(expiry, round(iv, 4), rng.randint(40, 900)))
        return OptionChain(symbol=symbol, spot=spot, expiries=expiries)

    # ------------------------------------------------------------ generation

    def all_bars(self) -> list[Bar]:
        out: list[Bar] = []
        for ref in self.get_universe():
            out.extend(self.series(ref))
        return out

    def shares_outstanding(self, symbol: str) -> float:
        rng = random.Random(_seed_for(symbol, self.seed + 3))
        # Log-uniform so the universe carries a few mega caps and a long tail.
        return round(10 ** rng.uniform(6.2, 9.9))

    def series(self, ref: TickerRef) -> list[Bar]:
        if ref.symbol in self._series:
            return self._series[ref.symbol]
        rng = random.Random(_seed_for(ref.symbol, self.seed + 1))
        if ref.type == "ETF":
            closes = self._path_index(rng, len(self.dates),
                                      market=(ref.symbol == self.benchmark))
            dates = self.dates
        else:
            archetype = random.Random(_seed_for(ref.symbol, self.seed)).choice(ARCHETYPES)
            if ref.list_date and ref.list_date > self.dates[0]:
                dates = [d for d in self.dates if d >= ref.list_date]
            else:
                dates = self.dates
            closes = self._path(rng, archetype, len(dates))
        bars = self._to_bars(ref.symbol, dates, closes, rng)
        self._series[ref.symbol] = bars
        return bars

    # -- path builders -------------------------------------------------

    @staticmethod
    def _walk(rng: random.Random, start: float, n: int, drift: float, vol: float) -> list[float]:
        out, px = [], start
        for _ in range(n):
            px *= (1.0 + drift + rng.gauss(0.0, vol))
            out.append(max(px, 0.5))
        return out

    def _path_index(self, rng: random.Random, n: int, market: bool) -> list[float]:
        start = rng.uniform(60, 480)
        drift = 0.00045 if market else rng.uniform(-0.0002, 0.0009)
        vol = 0.008 if market else rng.uniform(0.009, 0.016)
        closes = self._walk(rng, start, n, drift, vol)
        # One honest drawdown so "skip weak markets" has something to skip.
        if market and n > 160:
            lo, hi = int(n * 0.32), int(n * 0.46)
            for i in range(lo, hi):
                closes[i] *= 1.0 - 0.14 * ((i - lo) / max(1, hi - lo))
            after = closes[hi - 1] / closes[hi]
            for i in range(hi, n):
                closes[i] *= after
        return closes

    def _base(self, rng: random.Random, start_px: float, contractions: list[float],
              lengths: list[int]) -> list[float]:
        """A base: successive pullbacks from a shared ceiling, each shallower."""
        out: list[float] = []
        ceiling = start_px
        for depth, length in zip(contractions, lengths):
            down = max(4, int(length * 0.45))
            up = max(3, length - down)
            low = ceiling * (1.0 - depth)
            for i in range(down):
                t = (i + 1) / down
                out.append(ceiling - (ceiling - low) * t * (1.0 + rng.gauss(0, 0.02)))
            for i in range(up):
                t = (i + 1) / up
                target = ceiling * (1.0 - depth * 0.12)
                out.append(low + (target - low) * t * (1.0 + rng.gauss(0, 0.02)))
        return out

    def _path(self, rng: random.Random, archetype: str, n: int) -> list[float]:
        start = rng.uniform(3.5, 260)
        if archetype == "chop":
            return self._walk(rng, start, n, rng.uniform(-0.0004, 0.0005), rng.uniform(0.012, 0.026))
        if archetype == "laggard":
            closes = self._walk(rng, start, n, rng.uniform(-0.0016, -0.0002), rng.uniform(0.014, 0.030))
            return closes

        if archetype == "vcp":
            run = int(n * rng.uniform(0.48, 0.62))
            closes = self._walk(rng, start, run, rng.uniform(0.0016, 0.0032), 0.017)
            ceiling = closes[-1]
            depths = sorted([rng.uniform(0.14, 0.26), rng.uniform(0.07, 0.13),
                             rng.uniform(0.03, 0.06)], reverse=True)
            lens = [rng.randint(14, 24), rng.randint(10, 18), rng.randint(7, 12)]
            closes += self._base(rng, ceiling, depths, lens)
        elif archetype == "blue_sky":
            run = int(n * rng.uniform(0.62, 0.74))
            closes = self._walk(rng, start, run, rng.uniform(0.0020, 0.0036), 0.016)
            ceiling = max(closes)
            closes += self._base(rng, ceiling, [rng.uniform(0.08, 0.14), rng.uniform(0.04, 0.07)],
                                 [rng.randint(12, 20), rng.randint(9, 15)])
        elif archetype == "multi_year":
            fall = int(n * 0.22)
            closes = self._walk(rng, start, fall, -0.0032, 0.021)
            ceiling = start * rng.uniform(0.92, 1.02)
            flat = max(60, n - fall - int(n * 0.30))
            closes += self._walk(rng, closes[-1], flat, 0.0004, 0.020)
            recover = max(40, n - len(closes) - 30)
            lo = closes[-1]
            for i in range(recover):
                t = (i + 1) / recover
                closes.append(lo + (ceiling * 0.93 - lo) * t * (1.0 + rng.gauss(0, 0.015)))
            closes += self._base(rng, ceiling, [rng.uniform(0.06, 0.10)], [rng.randint(12, 20)])
        else:  # ipo
            run = max(20, int(n * rng.uniform(0.42, 0.58)))
            closes = self._walk(rng, start, run, rng.uniform(0.0018, 0.0040), 0.024)
            ceiling = closes[-1]
            closes += self._base(rng, ceiling, [rng.uniform(0.12, 0.22), rng.uniform(0.05, 0.09)],
                                 [rng.randint(11, 18), rng.randint(8, 13)])

        ceiling = max(closes[-60:]) if len(closes) >= 60 else max(closes)
        outcome = rng.random()
        remaining = n - len(closes)
        if remaining <= 0:
            return closes[:n]
        if outcome < 0.34:                       # breaks out and climbs
            thrust = min(remaining, rng.randint(2, 4))
            px = closes[-1]
            for i in range(thrust):
                px *= 1.0 + rng.uniform(0.025, 0.055)
                closes.append(px)
            closes += self._walk(rng, closes[-1], remaining - thrust, 0.0022, 0.018)
        elif outcome < 0.52:                     # broke out earlier, still climbing
            px = closes[-1] * rng.uniform(1.04, 1.09)
            closes.append(px)
            closes += self._walk(rng, px, remaining - 1, 0.0018, 0.019)
        elif outcome < 0.68:                     # broke out, failed, played out
            px = closes[-1] * 1.03
            closes.append(px)
            half = max(1, (remaining - 1) // 2)
            closes += self._walk(rng, px, half, -0.0045, 0.022)
            closes += self._walk(rng, closes[-1], remaining - 1 - half, -0.0008, 0.020)
        elif outcome < 0.80:                     # pokes the pivot and fails back in
            for _ in range(min(remaining, 2)):
                closes.append(ceiling * rng.uniform(0.995, 1.004))
            closes += self._walk(rng, closes[-1] * 0.97, max(0, remaining - 2), -0.0006, 0.014)
        else:                                    # still forming under the pivot
            closes += self._walk(rng, closes[-1], remaining, 0.0002, 0.012)
        return closes[:n]

    # -- OHLCV ---------------------------------------------------------

    def _to_bars(self, symbol: str, dates: list[dt.date], closes: list[float],
                 rng: random.Random) -> list[Bar]:
        closes = closes[-len(dates):]
        if len(closes) < len(dates):
            dates = dates[-len(closes):]
        # Volume scaled so the liquidity floor rejects a realistic minority.
        base_vol = 10 ** rng.uniform(4.2, 7.4)
        bars: list[Bar] = []
        prev = closes[0]
        n = len(closes)
        for i, (date, close) in enumerate(zip(dates, closes)):
            rel = abs(close / prev - 1.0)
            spread = max(0.004, rel * 1.2) * rng.uniform(0.6, 1.5)
            high = max(close, prev) * (1.0 + spread * rng.uniform(0.3, 1.0))
            low = min(close, prev) * (1.0 - spread * rng.uniform(0.3, 1.0))
            open_ = low + (high - low) * rng.uniform(0.2, 0.8)
            # Volume dries up through a base and expands on a thrust.
            vol = base_vol * rng.uniform(0.7, 1.4) * (1.0 + 14.0 * rel)
            if n - i < 120:
                vol *= 0.86
            bars.append(Bar(symbol, date, round(open_, 2), round(high, 2), round(low, 2),
                            round(close, 2), float(int(vol))))
            prev = close
        return bars
