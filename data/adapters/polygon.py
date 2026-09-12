"""Polygon.io free Basic, built around grouped daily aggregates.

One call returns every US ticker for one session, which is what makes a
whole-market scan fit inside a 5-calls-per-minute free tier.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence

import requests

from data import settings
from data.adapters.base import DataAdapter
from data.ratelimit import RateLimiter
from data.types import Bar, EarningsEvent, OptionChain, OptionExpiry, TickerRef

log = logging.getLogger(__name__)


class PolygonError(RuntimeError):
    pass


class PolygonGroupedAdapter(DataAdapter):
    name = "polygon"

    def __init__(self, api_key: str | None = None) -> None:
        cfg = settings.get("data.polygon", {}) or {}
        self.base_url = cfg.get("base_url", "https://api.polygon.io").rstrip("/")
        self.timeout = int(cfg.get("timeout_seconds", 30))
        self.api_key = api_key or settings.env(cfg.get("api_key_env", "POLYGON_API_KEY"))
        self.limiter = RateLimiter(int(cfg.get("calls_per_minute", 5)))
        self.session = requests.Session()

    # ------------------------------------------------------------ plumbing

    def _get(self, path_or_url: str, params: dict | None = None) -> dict:
        if not self.api_key:
            raise PolygonError(
                "POLYGON_API_KEY is not set. Export it, or set data.provider to "
                "'synthetic' in config/settings.yaml to work offline."
            )
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        params = dict(params or {})
        params["apiKey"] = self.api_key
        self.limiter.acquire()
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code == 429:
            # The limiter should prevent this; if the provider disagrees, wait it out once.
            self.limiter.acquire()
            resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code == 403:
            raise PolygonError(
                f"403 from {url.split('?')[0]} — this endpoint is not on the current plan. "
                "Grouped daily aggregates on free Basic is the premise of this build; "
                "verify it before going further."
            )
        if not resp.ok:
            raise PolygonError(f"{resp.status_code} from {url.split('?')[0]}: {resp.text[:200]}")
        return resp.json()

    # ------------------------------------------------------------ interface

    def get_universe(self) -> list[TickerRef]:
        out: list[TickerRef] = []
        payload = self._get("/v3/reference/tickers",
                            {"market": "stocks", "active": "true", "limit": 1000})
        while True:
            for row in payload.get("results", []):
                out.append(self._ref_from_row(row))
            nxt = payload.get("next_url")
            if not nxt:
                break
            payload = self._get(nxt)
        return out

    def get_grouped_daily(self, date: dt.date) -> list[Bar]:
        payload = self._get(
            f"/v2/aggs/grouped/locale/us/market/stocks/{date.isoformat()}",
            {"adjusted": "true"},
        )
        bars: list[Bar] = []
        for row in payload.get("results") or []:
            try:
                bars.append(Bar(
                    symbol=row["T"], date=date,
                    open=float(row["o"]), high=float(row["h"]),
                    low=float(row["l"]), close=float(row["c"]),
                    volume=float(row.get("v", 0.0)),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return bars

    def get_reference(self, symbol: str) -> TickerRef | None:
        try:
            payload = self._get(f"/v3/reference/tickers/{symbol}")
        except PolygonError as exc:
            log.warning("reference lookup failed for %s: %s", symbol, exc)
            return None
        row = payload.get("results")
        return self._ref_from_row(row) if row else None

    def get_earnings_dates(self, symbols: Sequence[str]) -> dict[str, list[EarningsEvent]]:
        from catalysts.yf import earnings_dates  # lazy: yfinance is optional
        return earnings_dates(symbols)

    def get_option_chain(self, symbol: str) -> OptionChain | None:
        from catalysts.yf import option_chain  # lazy: yfinance is optional
        return option_chain(symbol)

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _ref_from_row(row: dict) -> TickerRef:
        list_date = row.get("list_date")
        return TickerRef(
            symbol=row.get("ticker", ""),
            name=row.get("name", "") or "",
            type=row.get("type", "") or "",
            exchange=row.get("primary_exchange", "") or "",
            industry=(row.get("sic_description") or "").title(),
            list_date=dt.date.fromisoformat(list_date) if list_date else None,
            active=bool(row.get("active", True)),
        )


__all__ = ["PolygonGroupedAdapter", "PolygonError", "OptionExpiry"]
