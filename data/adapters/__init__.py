"""Adapter factory. The provider is chosen in config/settings.yaml."""
from __future__ import annotations

from data import settings
from data.adapters.base import DataAdapter


def get_adapter(provider: str | None = None) -> DataAdapter:
    name = (provider or settings.get("data.provider", "polygon")).lower()
    if name == "polygon":
        from data.adapters.polygon import PolygonGroupedAdapter
        return PolygonGroupedAdapter()
    if name == "synthetic":
        from data.adapters.synthetic import SyntheticAdapter
        return SyntheticAdapter()
    if name == "stooq":
        from data.adapters.stooq import StooqAdapter
        return StooqAdapter()
    if name == "eodhd":
        from data.adapters.eodhd import EODHDAdapter
        return EODHDAdapter()
    raise ValueError(f"unknown data.provider: {name!r}")


__all__ = ["DataAdapter", "get_adapter"]
