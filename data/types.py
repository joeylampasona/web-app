"""The shapes that cross the adapter boundary."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Bar:
    symbol: str
    date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class TickerRef:
    symbol: str
    name: str
    type: str = "CS"          # CS, ETF, ADRC, WARRANT, UNIT, PFD, …
    exchange: str = ""
    industry: str = ""
    list_date: dt.date | None = None
    active: bool = True


@dataclass(frozen=True)
class EarningsEvent:
    symbol: str
    date: dt.date
    confirmed: str = "tentative"     # confirmed | tentative | window


@dataclass
class OptionExpiry:
    expiry: dt.date
    implied_volatility: float        # mean IV across near-the-money contracts
    contracts: int = 0


@dataclass
class OptionContract:
    """One strike on one expiry, one side. What gamma concentration is built from.

    The chain is already downloaded for the implied-volatility reading, which
    keeps six near-the-money contracts per expiry and discards the rest. These
    are those same rows kept whole, so gamma costs no extra request.
    """
    expiry: dt.date
    side: str                        # "call" | "put"
    strike: float
    open_interest: int = 0
    implied_volatility: float = 0.0


@dataclass
class OptionChain:
    symbol: str
    spot: float
    expiries: list[OptionExpiry] = field(default_factory=list)
    # Every contract, not just the near-the-money summary above. Empty when the
    # source gave no usable rows, which the caller reports rather than hides.
    rows: list[OptionContract] = field(default_factory=list)
