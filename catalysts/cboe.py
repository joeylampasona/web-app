"""Option chains from Cboe's delayed-quote feed.

Why this and not the chain we already had: Yahoo returns a truncated book.
Its nearest Apple expiry carried 34 calls; Cboe carries 3,284 contracts for
the same name, across every listed expiry, and the site was building gamma
concentration — a statement about where the whole book anchors — out of a
few dozen strikes. It is also one request per company instead of nine, so
the deeper answer is the cheaper one.

Every field gamma needs is on each contract: open interest, implied
volatility, and the strike and expiry encoded in the contract symbol. No key
and no account. The figures are delayed, which does not matter here: open
interest is published once a day by OCC and is a day old at best from any
source, and the page says so.

Shapes here were taken from a probe run against the live endpoint rather
than from documentation, because this surface has none worth the name.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import threading
import time

import requests

from data import settings
from data.types import OptionChain, OptionContract, OptionExpiry

log = logging.getLogger(__name__)

BASE = "https://cdn.cboe.com/api/global/delayed_quotes/options"
TIMEOUT = 30

# A thousand-odd names go through here on a nightly, one request each. This is
# a CDN and not a rate-limited API, but a thousand requests as fast as the
# runner can issue them is rude and is the kind of thing that gets a free
# source closed to everybody. A tenth of a second costs the stage under two
# minutes and keeps it obviously well-behaved.
PAUSE = 0.1

# One connection, reused. Establishing a TLS session per name would cost more
# than the requests themselves.
_SESSION: requests.Session | None = None
_LOCK = threading.Lock()


def _session() -> requests.Session:
    global _SESSION                                # noqa: PLW0603
    with _LOCK:
        if _SESSION is None:
            _SESSION = requests.Session()
        return _SESSION

# How many near-the-money contracts make up an expiry's implied-volatility
# reading. Matches what the previous source used, so the High IV screen does
# not silently change meaning underneath itself.
NEAR_THE_MONEY = 6

# AAPL260921C00245000 -> root, 26-09-21, call, 245.000
#
# The OCC symbol: root, then the expiry as two-digit year, month and day, then
# C or P, then the strike in thousandths padded to eight digits. Anchored at
# both ends so a root containing a digit cannot be mistaken for a date.
_OCC = re.compile(r"^(?P<root>[A-Z0-9]{1,6}?)"
                  r"(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})"
                  r"(?P<side>[CP])"
                  r"(?P<strike>\d{8})$")


def parse_occ(symbol: str) -> tuple[dt.date, str, float] | None:
    """Expiry, side and strike from a contract symbol. None if it is not one."""
    match = _OCC.match((symbol or "").strip().upper())
    if not match:
        return None
    try:
        expiry = dt.date(2000 + int(match["yy"]), int(match["mm"]), int(match["dd"]))
    except ValueError:                             # 13th month, 32nd day
        return None
    strike = int(match["strike"]) / 1000.0
    if strike <= 0:
        return None
    return expiry, ("call" if match["side"] == "C" else "put"), strike


def _endpoint_symbol(symbol: str) -> str:
    """Cboe's spelling of a ticker. Class shares lose the dot: BRK.B is BRKB."""
    return symbol.strip().upper().replace(".", "").replace("-", "")


def _fetch(symbol: str) -> dict | None:
    url = f"{BASE}/{_endpoint_symbol(symbol)}.json"
    agent = (settings.get("edgar.user_agent")
             or settings.env("EDGAR_USER_AGENT", "")
             or "tape-research")
    try:
        response = _session().get(url, timeout=TIMEOUT, headers={
            "User-Agent": str(agent),
            "Accept": "application/json",
        })
        time.sleep(PAUSE)
        if response.status_code != 200:
            # 404 is ordinary: plenty of companies have no listed options.
            if response.status_code != 404:
                log.debug("cboe %s: HTTP %s", symbol, response.status_code)
            return None
        return response.json()
    except Exception as exc:                       # noqa: BLE001
        log.debug("cboe %s: %s", symbol, exc)
        return None


def _number(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if number != number else number     # NaN fails against itself


def chain(symbol: str, as_of: dt.date | None = None) -> OptionChain | None:
    """The whole listed book for one company, or None if it has none.

    Contracts without open interest or without an implied volatility are
    dropped rather than carried as zeros: a strike nobody holds contributes
    nothing to where the book anchors, and a zero would make a name look like
    it had no optionality rather than like we could not read it.
    """
    payload = _fetch(symbol)
    if not payload:
        return None
    data = payload.get("data") or {}
    options = data.get("options") or []
    if not options:
        return None

    spot = _number(data.get("close")) or _number(data.get("prev_day_close"))
    if spot <= 0:
        # Without the underlying's price there is no moneyness and no gamma.
        # Returning the chain anyway would repeat the exact fault this source
        # was brought in after: a section that renders empty while everything
        # upstream reports success.
        log.debug("cboe %s: no underlying price in the response", symbol)
        return None

    today = as_of or dt.date.today()
    rows: list[OptionContract] = []
    by_expiry: dict[dt.date, list[tuple[float, float]]] = {}
    for contract in options:
        parsed = parse_occ(contract.get("option") or "")
        if parsed is None:
            continue
        expiry, side, strike = parsed
        if expiry < today:
            continue
        open_interest = _number(contract.get("open_interest"))
        iv = _number(contract.get("iv"))
        if open_interest <= 0 or iv <= 0:
            continue
        rows.append(OptionContract(expiry=expiry, side=side, strike=strike,
                                   open_interest=int(open_interest),
                                   implied_volatility=iv))
        by_expiry.setdefault(expiry, []).append((abs(strike - spot), iv))

    if not rows:
        return None

    expiries: list[OptionExpiry] = []
    for expiry, pairs in sorted(by_expiry.items()):
        near = sorted(pairs)[:NEAR_THE_MONEY]
        if not near:
            continue
        expiries.append(OptionExpiry(
            expiry=expiry,
            implied_volatility=sum(iv for _, iv in near) / len(near),
            contracts=len(near),
        ))

    return OptionChain(symbol=symbol.upper(), spot=spot,
                       expiries=expiries, rows=rows)
