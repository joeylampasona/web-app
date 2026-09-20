"""Where open interest concentrates option gamma, by strike.

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT
---------------------------------------------

Gamma is the second derivative of an option's price with respect to the
underlying. Multiply one contract's gamma by the number of contracts
outstanding at that strike and you get a number that says: *a lot of optionality
is anchored here*. That is arithmetic over two published facts — the strike's
open interest and the contract's implied volatility — and it is what this module
reports.

It is NOT a claim about dealer positioning. The popular reading of this number
("dealers are long gamma above the flip and short below it, so price is pinned")
requires knowing who is long and who is short at each strike. Open interest does
not carry that. It says how many contracts exist, not who holds which side. The
convention that market makers are long calls and short puts is a heuristic, it
is disputed, and it is not in the data.

So two numbers are published per strike and they are not the same thing:

    concentration   unsigned. Sum of |gamma x OI| over calls and puts. A fact
                    about the option book. No assumption about anybody.

    net             signed, calls positive and puts negative — the conventional
                    "GEX". Published because it is what people expect to see,
                    labelled everywhere as resting on the positioning
                    assumption above.

A reader who trusts the convention can use `net`. A reader who does not still
gets `concentration`, which does not depend on it. Nothing here is advice, and
nothing here predicts where the price goes.

DATA QUALITY
------------

Open interest is published once a day by OCC and reaches our source with a lag,
so a level computed after tonight's close generally reflects the previous
session's book. That is fine for "where is the optionality anchored" and wrong
for anything presented as live, which is why nothing here is.

Every quantity is computed with the standard library. No new dependency.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
from dataclasses import dataclass, field

from data.types import OptionChain

log = logging.getLogger(__name__)

# One equity option covers this many shares.
CONTRACT_SIZE = 100

# Dollar gamma is quoted per 1% move in the underlying, which is what makes the
# number comparable between a $12 stock and a $900 one.
MOVE = 0.01

# Strikes further than this from spot contribute almost nothing and mostly add
# noise from stale far-dated open interest.
MAX_MONEYNESS = 0.30

# How many strikes to publish. Enough to see the shape around spot without
# shipping the whole book to a phone.
TOP_STRIKES = 12

# An option expiring today has no gamma worth reporting and divides by zero on
# the way to finding that out.
MIN_YEARS = 1.0 / 365.0

_SQRT_2PI = math.sqrt(2.0 * math.pi)


def _pdf(x: float) -> float:
    """Standard normal density. math.erf gives the CDF; this is its derivative."""
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def bs_gamma(spot: float, strike: float, sigma: float, years: float,
             rate: float = 0.0, dividend: float = 0.0) -> float:
    """Black-Scholes gamma for one contract. Calls and puts share it.

    Returns 0.0 rather than raising on the degenerate inputs that a scraped
    option chain supplies regularly: a zero or missing IV, an expiry today, a
    strike of zero. A gamma of zero contributes nothing to a sum, which is the
    right answer for a contract we cannot price.
    """
    if spot <= 0 or strike <= 0 or sigma <= 0 or years < MIN_YEARS:
        return 0.0
    try:
        vol_time = sigma * math.sqrt(years)
        d1 = (math.log(spot / strike)
              + (rate - dividend + 0.5 * sigma * sigma) * years) / vol_time
        return math.exp(-dividend * years) * _pdf(d1) / (spot * vol_time)
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0


@dataclass
class StrikeLevel:
    strike: float
    concentration: float      # unsigned dollar gamma per 1% move
    net: float                # calls minus puts, the conventional signing
    call_oi: int = 0
    put_oi: int = 0

    def to_json(self) -> dict:
        return {
            "strike": round(self.strike, 2),
            "concentration": round(self.concentration, 2),
            "net": round(self.net, 2),
            "call_oi": self.call_oi,
            "put_oi": self.put_oi,
        }


@dataclass
class GammaProfile:
    symbol: str
    spot: float
    as_of: dt.date
    levels: list[StrikeLevel] = field(default_factory=list)
    total_concentration: float = 0.0
    total_net: float = 0.0
    flip: float | None = None
    contracts: int = 0
    open_interest: int = 0
    expiries: int = 0

    def to_json(self) -> dict:
        return {
            "symbol": self.symbol,
            "spot": round(self.spot, 4),
            "as_of": self.as_of.isoformat(),
            "levels": [level.to_json() for level in self.levels],
            "total_concentration": round(self.total_concentration, 2),
            "total_net": round(self.total_net, 2),
            # Named for what it is: the strike where the CONVENTIONAL signing
            # crosses zero. Not "the level where dealers flip", which is a claim
            # about positions nobody published.
            "flip": round(self.flip, 2) if self.flip is not None else None,
            "contracts": self.contracts,
            "open_interest": self.open_interest,
            "expiries": self.expiries,
        }


def profile(chain: OptionChain, as_of: dt.date, rate: float = 0.0,
            horizon_days: int = 90) -> GammaProfile | None:
    """Aggregate one chain into per-strike gamma. None when there is nothing to say.

    `rate` is the risk-free rate as a decimal. Gamma is not very sensitive to
    it — a full percentage point moves ATM gamma by well under one percent — so
    a missing rate degrades the number slightly rather than invalidating it.
    """
    if chain is None or chain.spot <= 0 or not chain.rows:
        return None

    horizon = as_of + dt.timedelta(days=horizon_days)
    spot = chain.spot
    by_strike: dict[float, StrikeLevel] = {}
    contracts = 0
    total_oi = 0
    expiries: set[dt.date] = set()

    for row in chain.rows:
        if row.expiry < as_of or row.expiry > horizon:
            continue
        if row.strike <= 0 or abs(row.strike - spot) / spot > MAX_MONEYNESS:
            continue
        oi = int(row.open_interest or 0)
        if oi <= 0:
            continue
        years = max((row.expiry - as_of).days / 365.0, 0.0)
        gamma = bs_gamma(spot, row.strike, float(row.implied_volatility or 0.0),
                         years, rate)
        if gamma <= 0:
            continue

        # Dollar gamma per 1% move, for this strike's whole open interest.
        dollars = gamma * oi * CONTRACT_SIZE * spot * spot * MOVE
        level = by_strike.setdefault(row.strike, StrikeLevel(row.strike, 0.0, 0.0))
        level.concentration += dollars
        if row.side == "call":
            level.net += dollars
            level.call_oi += oi
        else:
            level.net -= dollars
            level.put_oi += oi
        contracts += 1
        total_oi += oi
        expiries.add(row.expiry)

    if not by_strike:
        return None

    ordered = sorted(by_strike.values(), key=lambda level: level.strike)
    top = sorted(by_strike.values(), key=lambda level: -level.concentration)[:TOP_STRIKES]
    return GammaProfile(
        symbol=chain.symbol,
        spot=spot,
        as_of=as_of,
        levels=sorted(top, key=lambda level: level.strike),
        total_concentration=sum(level.concentration for level in ordered),
        total_net=sum(level.net for level in ordered),
        flip=_flip(ordered),
        contracts=contracts,
        open_interest=total_oi,
        expiries=len(expiries),
    )


def _flip(levels: list[StrikeLevel]) -> float | None:
    """The strike where the conventionally-signed running total crosses zero.

    Walked from the lowest strike up, because that is the direction the
    cumulative reading is defined in. Returns None when the total never changes
    sign, which is a real and common state — not every name has a crossing, and
    inventing one by clamping to an end of the range would put a line on a chart
    that means nothing.
    """
    running = 0.0
    previous: StrikeLevel | None = None
    for level in levels:
        before = running
        running += level.net
        if previous is not None and before != 0.0 and (before > 0) != (running > 0):
            # Linear interpolation between the two strikes that straddle zero.
            span = running - before
            if span == 0:
                return level.strike
            weight = -before / span
            return previous.strike + (level.strike - previous.strike) * weight
        previous = level
    return None


# ---------------------------------------------------------------- storage
#
# The catalysts stage fetches and writes; publish reads and never reaches the
# network. A stored profile outlives the night it was fetched, so a throttled
# run costs the names it missed rather than emptying the section.

# How old a stored profile may be before the site stops showing it. Open
# interest moves slowly, but a week-old book presented beside today's price is
# a different statement from a yesterday-old one.
MAX_AGE_DAYS = 5


def store(conn, profiles: dict[str, GammaProfile]) -> int:
    """Keep what was computed. Returns rows written."""
    import json                                   # noqa: PLC0415

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    written = 0
    for symbol, found in profiles.items():
        conn.execute(
            "INSERT OR REPLACE INTO gamma_profiles"
            "(symbol, as_of, payload, fetched_at) VALUES (?,?,?,?)",
            (symbol.upper(), found.as_of.isoformat(),
             json.dumps(found.to_json(), separators=(",", ":")), now))
        written += 1
    conn.commit()
    return written


def load(conn, symbols, as_of: dt.date,
         max_age_days: int = MAX_AGE_DAYS) -> dict[str, dict]:
    """Stored profiles for these names, as published JSON. Stale ones excluded."""
    import json                                   # noqa: PLC0415

    wanted = {s.upper() for s in symbols}
    cutoff = (as_of - dt.timedelta(days=max_age_days)).isoformat()
    out: dict[str, dict] = {}
    for row in conn.execute(
            "SELECT symbol, as_of, payload FROM gamma_profiles WHERE as_of >= ?",
            (cutoff,)):
        symbol = row[0]
        if symbol not in wanted:
            continue
        try:
            payload = json.loads(row[2])
        except (TypeError, ValueError):
            continue
        # The reader needs to know the book may predate the price beside it.
        payload["stale"] = row[1] < as_of.isoformat()
        out[symbol] = payload
    return out
