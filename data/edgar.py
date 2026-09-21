"""Shares outstanding from SEC EDGAR companyfacts. Free, no key, but it asks
for a contactable user agent and it rate-limits at 10 requests a second."""
from __future__ import annotations

import datetime as dt
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

# How SEC might spell a ticker this site spells with a dot.
#
# Share classes are the whole problem. This site calls Berkshire's B shares
# BRK.B and SEC's ticker file calls them BRK-B, so the lookup missed, no share
# count came back, and the company was dropped from the universe — a
# difference in punctuation reported as a fact about the company. Cheap to try
# every spelling, and the map is a dictionary, so the cost is a few lookups.
def _cik_candidates(symbol: str) -> list[str]:
    upper = symbol.upper()
    out = [upper]
    for variant in (upper.replace(".", "-"), upper.replace("-", "."),
                    upper.replace(".", ""), upper.replace("-", "")):
        if variant not in out:
            out.append(variant)
    return out


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


# How old a reported share count may be before it stops meaning anything.
# Berkshire's dei concept still returns a 2011 figure as its newest entry, and
# a fifteen-year-old count turned into a market cap is not a worse number, it
# is a different company's number.
SHARES_MAX_AGE_DAYS = 400

# Where to look, in order. The dei cover-page concept is the right answer when
# it exists. It does not always exist: SEC returns a flat 404 for Meta and for
# Alphabet, both of which simply do not tag it, and those two absences are why
# neither company had a page on this site. The us-gaap fallbacks carry the
# whole-company total for exactly those filers — Alphabet's
# CommonStockSharesOutstanding is 12.23bn across all classes, Meta's basic
# weighted average is 2.54bn — which is the number a market cap wants.
_SHARE_CONCEPTS = (
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
    ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),
)

# A refusal is about us; retry it once rather than record it as an absence.
# Every throttled request that goes down as "this company has no share count"
# drops a real company from the universe for a reason that has nothing to do
# with the company, which is the fault this whole module keeps producing.
THROTTLE_STATUSES = (401, 403, 429, 503)
THROTTLE_PAUSE = 2.0
REQUEST_PAUSE = 0.11                               # stay under 10 req/s

# Why a symbol has no share count. Counted every run and printed, because
# "SEC does not tag this company" and "SEC would not talk to us" and "we
# spelled the ticker differently" are three different faults that produced one
# indistinguishable silence.
NO_CIK = "no CIK for this ticker at SEC"
NOT_TAGGED = "SEC has no such concept for this company"
TOO_OLD = f"newest filed count is over {SHARES_MAX_AGE_DAYS} days old"
THROTTLED = "SEC refused the request"
ERRORED = "the request failed"


def _newest_share_count(units: list[dict], today: dt.date) -> float | None:
    """The most recent usable value, or None if the newest one is too old."""
    dated = [u for u in units if u.get("end") and (u.get("val") or 0) > 0]
    if not dated:
        return None
    latest = max(dated, key=lambda u: u["end"])
    try:
        end = dt.date.fromisoformat(latest["end"])
    except (TypeError, ValueError):
        return None
    if (today - end).days > SHARES_MAX_AGE_DAYS:
        return None
    return float(latest["val"])


def shares_outstanding(symbols: Iterable[str], progress=None,
                       reasons: dict[str, str] | None = None) -> dict[str, float]:
    """Latest reported shares outstanding per symbol. Missing symbols are absent.

    `reasons` is filled in for every symbol that comes back without a count,
    with one of the constants above. Callers use it to say why a company was
    dropped instead of only that it was — the difference between "SEC does not
    publish this" and "SEC would not talk to us tonight" decides whether
    anybody should do anything about it.

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
    why: dict[str, str] = reasons if reasons is not None else {}
    refused = 0
    total = len(symbols)
    today = dt.date.today()

    def ask(cik: str, taxonomy: str, concept: str):
        """One concept, retried once if SEC refuses rather than answers."""
        url = f"{base}/api/xbrl/companyconcept/{cik}/{taxonomy}/{concept}.json"
        resp = None
        for attempt in (0, 1):
            resp = session.get(url, headers={"User-Agent": _user_agent()},
                               timeout=30)
            time.sleep(REQUEST_PAUSE)
            if resp.status_code in THROTTLE_STATUSES and attempt == 0:
                time.sleep(THROTTLE_PAUSE)
                continue
            break
        return resp

    for index, sym in enumerate(symbols, 1):
        # One request per company at SEC's rate limit is minutes of silence
        # otherwise, which is indistinguishable from a hang.
        if progress and (index % 100 == 0 or index == total):
            progress(index, total, len(out))

        cik = next((cik_map[name] for name in _cik_candidates(sym)
                    if name in cik_map), None)
        if not cik:
            why[sym] = NO_CIK
            continue

        # Each concept in turn, stopping at the first that answers. Almost
        # every company is served by the first one and costs a single request;
        # only the handful that do not tag it pay for the others. The reason
        # recorded is the most specific one seen: a company that was throttled
        # on one concept and 404s on the rest was throttled, not untagged.
        verdict = NOT_TAGGED
        for taxonomy, concept in _SHARE_CONCEPTS:
            try:
                resp = ask(cik, taxonomy, concept)
                if resp.status_code != 200:
                    # 404 means this company does not tag this concept, which
                    # is ordinary and is exactly why there is a list of them.
                    # A refusal is about us, not about the company, and if it
                    # happens to every company it is an outage wearing a
                    # per-company disguise.
                    if resp.status_code in THROTTLE_STATUSES:
                        refused += 1
                        verdict = THROTTLED
                    continue
                units = resp.json().get("units", {}).get("shares", [])
                value = _newest_share_count(units, today)
                if value is None:
                    if units and verdict == NOT_TAGGED:
                        verdict = TOO_OLD
                    continue
                out[sym] = value
                break
            except Exception as exc:               # noqa: BLE001
                verdict = ERRORED
                log.debug("EDGAR %s/%s failed for %s: %s",
                          taxonomy, concept, sym, exc)
        if sym not in out:
            why[sym] = verdict

    if why:
        tally: dict[str, int] = {}
        for reason in why.values():
            tally[reason] = tally.get(reason, 0) + 1
        for reason, count in sorted(tally.items(), key=lambda kv: -kv[1]):
            log.info("share counts: %d symbol(s) — %s", count, reason)

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
