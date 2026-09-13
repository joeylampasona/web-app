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


class EdgarUnavailable(RuntimeError):
    """SEC could not be reached at all, as opposed to not knowing one company.

    These are different failures and they must not look the same. One company
    without a filed share count is normal and the universe carries on without
    it. SEC refusing every request means no company has a market cap, which
    silently empties the whole universe — so it is raised, not logged.
    """


def _user_agent() -> str:
    cfg = settings.get("edgar", {}) or {}
    return settings.env(cfg.get("user_agent_env", "EDGAR_USER_AGENT"),
                        cfg.get("default_user_agent", "base-and-breakout-site"))


_CIK_CACHE: dict[str, str] | None = None


def _ticker_to_cik(session: requests.Session) -> dict[str, str]:
    global _CIK_CACHE
    if _CIK_CACHE is not None:
        return _CIK_CACHE
    url = "https://www.sec.gov/files/company_tickers.json"
    agent = _user_agent()
    try:
        resp = session.get(url, headers={"User-Agent": agent}, timeout=30)
    except Exception as exc:                       # noqa: BLE001 - network shape varies
        raise EdgarUnavailable(
            f"Could not reach SEC at {url}: {exc}") from exc
    if resp.status_code != 200:
        hint = ""
        if resp.status_code in (401, 403, 429):
            hint = (" SEC refuses requests without a contactable User-Agent, and "
                    "rate-limits hard from shared cloud addresses. This run sent "
                    f"{agent!r} — set EDGAR_USER_AGENT to something like "
                    "'Your Name your@email.com'.")
        raise EdgarUnavailable(
            f"SEC returned HTTP {resp.status_code} for the ticker map.{hint}")
    out: dict[str, str] = {}
    for row in json.loads(resp.text).values():
        out[str(row["ticker"]).upper()] = f"CIK{int(row['cik_str']):010d}"
    _CIK_CACHE = out
    return out


def shares_outstanding(symbols: Iterable[str],
                       progress=None) -> dict[str, float]:
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
    # Deliberately not caught. A caller that cannot get share counts cannot
    # compute a market cap, and a universe filtered on a market cap nobody
    # knows is an empty universe that reports success.
    cik_map = _ticker_to_cik(session)

    out: dict[str, float] = {}
    refused = 0
    total = len(symbols)
    for index, sym in enumerate(symbols, 1):
        # One request per company at SEC's rate limit is minutes of silence
        # otherwise, which is indistinguishable from a hang.
        if progress and (index % 100 == 0 or index == total):
            progress(index, total, len(out))
        cik = cik_map.get(sym)
        if not cik:
            continue
        try:
            resp = session.get(f"{base}/api/xbrl/companyconcept/{cik}/dei/"
                               f"EntityCommonStockSharesOutstanding.json",
                               headers={"User-Agent": _user_agent()}, timeout=30)
            time.sleep(0.11)                       # stay under 10 req/s
            if resp.status_code != 200:
                # 404 means SEC has no such filing, which is ordinary. A refusal
                # is about us, not about the company, and if it happens to every
                # company it is an outage wearing a per-company disguise.
                if resp.status_code in (401, 403, 429):
                    refused += 1
                continue
            units = resp.json().get("units", {}).get("shares", [])
            if not units:
                continue
            latest = max(units, key=lambda u: u.get("end", ""))
            out[sym] = float(latest["val"])
        except Exception as exc:                   # noqa: BLE001
            log.debug("EDGAR lookup failed for %s: %s", sym, exc)

    # Asked about real companies and told no by all of them: that is SEC
    # refusing us, not the market having no shares outstanding.
    if not out and refused:
        raise EdgarUnavailable(
            f"SEC refused all {refused:,} share-count requests. Check "
            "EDGAR_USER_AGENT is a contactable string such as "
            "'Your Name your@email.com'.")
    return out


def industries(symbols: Iterable[str], progress=None) -> dict[str, str]:
    """Standard industry description per symbol, from SEC's submissions file.

    Polygon's ticker *list* endpoint does not carry an industry — only the
    per-ticker details endpoint does, and 2,000 of those at five calls a minute
    is seven hours. SEC allows ten requests a second, so the same coverage takes
    about four minutes.

    Anything missing is simply absent from the result, which leaves the caller
    with the same "Unclassified" it would have had anyway.
    """
    symbols = [s.upper() for s in symbols]
    if settings.get("data.provider") == "synthetic":
        return {}

    base = (settings.get("edgar.base_url") or "https://data.sec.gov").rstrip("/")
    session = requests.Session()
    # Caught here, unlike in shares_outstanding, and the asymmetry is the point:
    # a missing industry leaves a name "Unclassified", which is a degraded page.
    # A missing share count removes the name from the universe entirely.
    try:
        cik_map = _ticker_to_cik(session)
    except Exception as exc:                      # noqa: BLE001
        log.warning("EDGAR ticker map unavailable, industries will be blank: %s", exc)
        return {}

    out: dict[str, str] = {}
    total = len(symbols)
    for index, sym in enumerate(symbols, 1):
        if progress and (index % 100 == 0 or index == total):
            progress(index, total, len(out))
        cik = cik_map.get(sym)
        if not cik:
            continue
        try:
            resp = session.get(f"{base}/submissions/{cik}.json",
                               headers={"User-Agent": _user_agent()}, timeout=30)
            time.sleep(0.11)                       # stay under 10 req/s
            if resp.status_code != 200:
                continue
            payload = resp.json()
            # Field name defended rather than assumed.
            label = (payload.get("sicDescription")
                     or payload.get("sic_description")
                     or "")
            if not label:
                code = payload.get("sic") or payload.get("sicCode")
                label = f"SIC {code}" if code else ""
            if label:
                out[sym] = str(label).strip().title()
        except Exception as exc:                   # noqa: BLE001
            log.debug("EDGAR industry lookup failed for %s: %s", sym, exc)
    return out
