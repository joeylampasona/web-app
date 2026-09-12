"""The one interface every provider implements."""
from __future__ import annotations

import abc
import datetime as dt
from collections.abc import Sequence

from data.types import Bar, EarningsEvent, OptionChain, TickerRef


class DataAdapter(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    def get_universe(self) -> list[TickerRef]:
        """Every tradable reference row the provider knows about."""

    @abc.abstractmethod
    def get_grouped_daily(self, date: dt.date) -> list[Bar]:
        """One call, every US ticker, one session. [] on a non-trading day."""

    @abc.abstractmethod
    def get_reference(self, symbol: str) -> TickerRef | None:
        """Type, exchange, name, industry and list date for one symbol."""

    @abc.abstractmethod
    def get_earnings_dates(self, symbols: Sequence[str]) -> dict[str, list[EarningsEvent]]:
        """Confirmed and estimated earnings dates, screen population only."""

    @abc.abstractmethod
    def get_option_chain(self, symbol: str) -> OptionChain | None:
        """Expiries with per-expiry mean IV. None when there are no listed options."""
