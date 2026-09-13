"""EODHD — paid provider kept as a migration path. Not implemented."""
from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from data.adapters.base import DataAdapter
from data.types import Bar, EarningsEvent, OptionChain, TickerRef

_MSG = "EODHDAdapter is a stub. It is a paid provider; wiring it is a stop condition."


class EODHDAdapter(DataAdapter):
    name = "eodhd"

    def get_universe(self) -> list[TickerRef]:
        raise NotImplementedError(_MSG)

    def get_grouped_daily(self, date: dt.date) -> list[Bar]:
        raise NotImplementedError(_MSG)

    def get_reference(self, symbol: str) -> TickerRef | None:
        raise NotImplementedError(_MSG)

    def get_earnings_dates(self, symbols: Sequence[str]) -> dict[str, list[EarningsEvent]]:
        raise NotImplementedError(_MSG)

    def get_option_chain(self, symbol: str) -> OptionChain | None:
        raise NotImplementedError(_MSG)
