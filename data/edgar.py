"""Shares outstanding from SEC EDGAR companyfacts. Free, no key, but it asks
for a contactable user agent and it rate-limits at 10 requests a second."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable

import requests

from data import settings

log = logging.getLogger(__name__)

_TAGS = ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding",
         "CommonStockSharesIssued")


def _user_agent() -> str:
    cfg = settings.get("edgar", {}) or {}
    return settings.env(cfg.get("user_agent_env", "EDGAR_USER_AGENT"),
                        cfg.get("default_user_agent", "base-and-breakout-site"))


def _ticker_to_cik(session: requests.Session) -> dict[str, str]:
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = session.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
    resp.raise_for_status()
    out: dict[str, str] = {}
    for row in json.loads(resp.text).values():
        out[str(row["ticker"]).upper()] = f"CIK{int(row['cik_str']):010d}"
    return out


def shares_outstanding(symbols: Iterable[str]) -> dict[str, float]:
    """Latest reported shares outstanding per symbol. Missing symbols are absent.

    With the synthetic provider this returns deterministic fixture counts
    rather than hitting SEC, so the funnel is reproducible offline.
    """
    symbols = [s.upper() for s in symbols]
    if settings.get("data.provider") == "synthetic":
        from data.adapters.synthetic import SyntheticAdapter
        adapter = SyntheticAdapter()
        return {s: adapter.shares_outstanding(s) for s in symbols}

    base = (settings.get("edgar.base_url") or "https://data.sec.gov").rstrip("/")
    session = requests.Session()
    try:
        cik_map = _ticker_to_cik(session)
    except Exception as exc:                      # noqa: BLE001 - network shape varies
        log.warning("EDGAR ticker map unavailable: %s", exc)
        return {}

    out: dict[str, float] = {}
    for sym in symbols:
        cik = cik_map.get(sym)
        if not cik:
            continue
        try:
            resp = session.get(f"{base}/api/xbrl/companyconcept/{cik}/dei/"
                               f"EntityCommonStockSharesOutstanding.json",
                               headers={"User-Agent": _user_agent()}, timeout=30)
            time.sleep(0.11)                       # stay under 10 req/s
            if resp.status_code != 200:
                continue
            units = resp.json().get("units", {}).get("shares", [])
            if not units:
                continue
            latest = max(units, key=lambda u: u.get("end", ""))
            out[sym] = float(latest["val"])
        except Exception as exc:                   # noqa: BLE001
            log.debug("EDGAR lookup failed for %s: %s", sym, exc)
    return out
