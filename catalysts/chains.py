"""One company's option book, joined from two free sources.

    OCC      open interest for every listed series. The clearing house's own
             figure, the whole book, one request a company.
    Yahoo    an implied volatility for each contract, one request an expiry.

Cboe used to give both in one document and has refused the nightly since
2026-11-19. Yahoo alone was the fallback, and its open interest covers a
fraction of the book: the first night without Cboe the gamma board went from
461 companies to 225.

How the two are joined, so nobody reads more into a row than is there:

  * Open interest is OCC's wherever OCC answered. A series OCC lists and
    Yahoo does not is kept, on any expiry Yahoo was asked about.
  * Yahoo gives every contract an implied volatility, and where there is
    no quote it derives one from the last trade, however old. So a figure
    is believed only where the contract has a two-sided quote no wider than
    half its own mid, or traded on the chain's latest session, and only
    between 3% and 500%. Market Desk found the same thing the same evening:
    on thin names the unbelieved figures put skew at 160 points.
  * A contract without a believed figure takes the nearest strike's on the
    same expiry: its own side first, then the other side, then the nearest
    expiry that has one. Gamma is not sensitive enough to a neighbouring
    strike's volatility for that to move a level.
  * The per-expiry reading the High IV page ranks is built only from
    volatilities Yahoo actually quoted, never from borrowed ones.
  * If OCC did not answer, Yahoo's own open interest stands and the chain
    says so in `source`, which is what marks a gamma row "partial".
"""
from __future__ import annotations

import collections
import datetime as dt
import logging
import zoneinfo

from catalysts import occ, yf
from data.types import OptionChain, OptionContract, OptionExpiry

log = logging.getLogger(__name__)

#: Outside this an implied volatility is a placeholder, not a reading.
IV_LOW, IV_HIGH = 0.03, 5.0

#: How far out Yahoo is asked, in days. Gamma looks ninety days ahead; the
#: few extra cover an expiry that falls just past it by today's date and
#: inside it by the session's.
HORIZON_DAYS = 95

#: Never fewer than this many expiries, however far out they are. A company
#: with quarterly expiries only would otherwise bring one, and the High IV
#: reading needs the expiry either side of an event.
MIN_EXPIRIES = 4

#: Never more than this many. A handful of the largest companies list an
#: expiry most days of the week, and a request each is the cost.
MAX_EXPIRIES = 30

#: How many near-the-money contracts a side contributes to an expiry's
#: reading. Unchanged from the Yahoo-only chain, so the High IV page does not
#: change meaning underneath itself.
NEAR_THE_MONEY = 6

#: What happened to every company asked about in this process.
OUTCOMES: "collections.Counter[str]" = collections.Counter()

_NEW_YORK = zoneinfo.ZoneInfo("America/New_York")


def today() -> dt.date:
    return dt.datetime.now(_NEW_YORK).date()


def usable(iv) -> bool:
    return iv is not None and iv == iv and IV_LOW <= iv <= IV_HIGH


def wide(bid: float, ask: float) -> bool:
    """A two-sided quote too wide to be a price: more than half its own mid
    apart, and more than a dime. What a quote left over from the close looks
    like at two in the morning."""
    return bid > 0 and ask > 0 and (ask - bid) > max(0.25 * (bid + ask), 0.10)


def believed(row: dict) -> bool:
    """Whether Yahoo's implied volatility for this contract is a reading."""
    bid, ask = row.get("bid", 0.0), row.get("ask", 0.0)
    if not usable(row.get("iv")) or wide(bid, ask):
        return False
    return (bid > 0 and ask > 0) or bool(row.get("fresh"))


def join(symbol: str, spot: float, quoted: list[dict],
         book: occ.Book | None) -> OptionChain | None:
    """The chain from Yahoo's rows and OCC's book. `book` None keeps Yahoo's
    own open interest. Pure: no network, so it can be tested on a table."""
    if not quoted or spot <= 0:
        return None

    # 1. Decide which volatilities are readings.
    for row in quoted:
        row["own_iv"] = row["iv"] if believed(row) else 0.0

    # 2. The per-expiry reading, from quoted volatilities only.
    expiries: list[OptionExpiry] = []
    asked = sorted({row["expiry"] for row in quoted})
    for expiry in asked:
        near: list[float] = []
        for side in ("call", "put"):
            mine = sorted((abs(r["strike"] - spot), r["own_iv"]) for r in quoted
                          if r["expiry"] == expiry and r["side"] == side)
            near.extend(iv for _, iv in mine[:NEAR_THE_MONEY] if iv > 0)
        if near:
            expiries.append(OptionExpiry(expiry, sum(near) / len(near), len(near)))

    # 3. Open interest: OCC's where there is one, and the series only it has.
    rows = [dict(r) for r in quoted]
    if book is not None:
        seen = set()
        for row in rows:
            key = (row["expiry"], row["side"], row["strike"])
            seen.add(key)
            row["oi"] = book.get(key, 0)
        wanted = set(asked)
        for (expiry, side, strike), held in book.items():
            if held > 0 and expiry in wanted and (expiry, side, strike) not in seen:
                rows.append({"expiry": expiry, "side": side, "strike": strike,
                             "oi": held, "own_iv": 0.0})

    # 4. A contract without a reading borrows the nearest strike's.
    known: dict[tuple[dt.date, str], list[tuple[float, float]]] = {}
    by_expiry: dict[dt.date, list[tuple[float, float]]] = {}
    for row in rows:
        if row["own_iv"] > 0:
            known.setdefault((row["expiry"], row["side"]), []).append(
                (row["strike"], row["own_iv"]))
            by_expiry.setdefault(row["expiry"], []).append(
                (row["strike"], row["own_iv"]))
    contracts: list[OptionContract] = []
    for row in rows:
        held = int(row.get("oi") or 0)
        if held <= 0:
            continue
        iv = row["own_iv"]
        if iv <= 0:
            other = "put" if row["side"] == "call" else "call"
            pool = known.get((row["expiry"], row["side"])) \
                or known.get((row["expiry"], other))
            if not pool and by_expiry:
                nearest = min(by_expiry, key=lambda e: (
                    abs((e - row["expiry"]).days), e))
                pool = by_expiry[nearest]
            if not pool:
                continue
            iv = min(pool, key=lambda p: (abs(p[0] - row["strike"]), p[0]))[1]
        contracts.append(OptionContract(expiry=row["expiry"], side=row["side"],
                                        strike=row["strike"], open_interest=held,
                                        implied_volatility=iv))

    if not expiries and not contracts:
        return None
    return OptionChain(symbol=symbol.upper(), spot=spot, expiries=expiries,
                       rows=contracts,
                       source="occ+yahoo" if book is not None else "yahoo")


def build(symbol: str, as_of: dt.date | None = None) -> OptionChain | None:
    """The chain for one company, or None when it has none worth reading."""
    book = occ.open_interest(symbol)
    if book is not None and not any(held > 0 for held in book.values()):
        # The clearing house answered and holds nothing. Yahoo is not asked:
        # a third of the names the nightly asks about have no listed options,
        # and that is several hundred requests a night not made.
        OUTCOMES["no_listed_options"] += 1
        return None
    spot, quoted = yf.quoted_chain(symbol, as_of or today(),
                                   horizon_days=HORIZON_DAYS,
                                   at_least=MIN_EXPIRIES, at_most=MAX_EXPIRIES)
    chain = join(symbol, spot, quoted, book)
    if chain is None:
        OUTCOMES["yahoo_had_none"] += 1
        return None
    OUTCOMES[chain.source] += 1
    # The day's option volume rides on the same rows: no request is made for it.
    try:
        from catalysts import optvol               # noqa: PLC0415 - avoids a cycle
        chain.activity = optvol.summary(symbol, spot, quoted, book)
    except Exception as exc:                       # noqa: BLE001 - never cost the chain
        log.debug("option volume for %s: %s", symbol, exc)
    return chain
