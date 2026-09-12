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
class OptionChain:
    symbol: str
    spot: float
    expiries: list[OptionExpiry] = field(default_factory=list)
