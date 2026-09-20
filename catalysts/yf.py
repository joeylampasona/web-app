"""yfinance-backed earnings dates and option chains.

yfinance scrapes an undocumented endpoint. It breaks without notice and rate
limits opaquely, so every call here degrades to empty rather than raising: a
missing earnings date costs a badge, a failed nightly run costs the whole site.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence

from data.types import EarningsEvent, OptionChain, OptionContract, OptionExpiry

log = logging.getLogger(__name__)


def _yf():
    try:
        import yfinance  # noqa: PLC0415 - optional dependency, imported lazily
        return yfinance
    except Exception as exc:                      # noqa: BLE001
        log.warning("yfinance unavailable (%s) — earnings and IV will be empty", exc)
        return None


def earnings_dates(symbols: Sequence[str]) -> dict[str, list[EarningsEvent]]:
    yf = _yf()
    out: dict[str, list[EarningsEvent]] = {}
    if yf is None:
        return out
    for symbol in symbols:
        try:
            frame = yf.Ticker(symbol).get_earnings_dates(limit=8)
            if frame is None or frame.empty:
                continue
            events: list[EarningsEvent] = []
            for stamp, row in frame.iterrows():
                date = stamp.date() if hasattr(stamp, "date") else stamp
                reported = row.get("Reported EPS")
                confirmed = "confirmed" if reported == reported and reported is not None \
                    else "tentative"
                events.append(EarningsEvent(symbol, date, confirmed))
            if events:
                out[symbol] = events
        except Exception as exc:                  # noqa: BLE001
            log.debug("earnings lookup failed for %s: %s", symbol, exc)
    return out


def option_chain(symbol: str) -> OptionChain | None:
    yf = _yf()
    if yf is None:
        return None
    try:
        ticker = yf.Ticker(symbol)
        expiries = list(ticker.options or [])
        if not expiries:
            return None
        spot = _spot_price(ticker.fast_info)
        rows: list[OptionExpiry] = []
        # Every contract, kept alongside the near-the-money IV summary. The
        # download is the expensive part and it already happened; discarding
        # these rows and fetching them again for gamma would double the cost of
        # the slowest stage in the nightly.
        contracts: list[OptionContract] = []
        for text in expiries[:8]:
            chain = ticker.option_chain(text)
            expiry = dt.date.fromisoformat(text)
            sides = (("call", chain.calls), ("put", chain.puts))
            frames = [f for _, f in sides if f is not None and not f.empty]
            for side, frame in sides:
                if frame is None or frame.empty:
                    continue
                contracts.extend(_contracts(frame, expiry, side))
            if not frames:
                continue
            ivs: list[float] = []
            for frame in frames:
                near = frame.copy()
                if spot and "strike" in near:
                    near["distance"] = (near["strike"] - spot).abs()
                    near = near.nsmallest(6, "distance")
                ivs.extend(float(v) for v in near.get("impliedVolatility", [])
                           if v == v and v > 0)
            if ivs:
                rows.append(OptionExpiry(expiry, sum(ivs) / len(ivs), len(ivs)))
        if not rows and not contracts:
            return None
        return OptionChain(symbol=symbol, spot=spot, expiries=rows, rows=contracts)
    except Exception as exc:                      # noqa: BLE001
        log.debug("option chain failed for %s: %s", symbol, exc)
        return None



# The keys a spot price has been known to arrive under, in preference order.
#
# `last_price` is not among them, and it was the only one we asked for. The
# call returned None for every name, spot became 0.0, and gamma's profile()
# returns None the moment spot is not positive — so every company on the site
# reported "no usable open interest" while the open interest was sitting there
# untouched. Implied volatility came off the same chains and was fine, because
# it only uses spot to sort for the near-the-money strikes and guards that with
# `if spot`. One field name, and the difference between a section that works
# and a section that has never once had a row in it.
#
# Several keys rather than the correct one alone: this is an undocumented
# surface that has already renamed this field once.
_SPOT_KEYS = ("lastPrice", "last_price", "regularMarketPrice",
              "previousClose", "previous_close")


def _spot_price(info) -> float:
    """The underlying's price from a fast-info mapping, or 0.0 if none of the
    keys it might use carry one."""
    for key in _SPOT_KEYS:
        try:
            value = info.get(key)
        except Exception:                          # noqa: BLE001
            continue
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return 0.0


def _contracts(frame, expiry: dt.date, side: str) -> list[OptionContract]:
    """One side of one expiry, as plain rows.

    Open interest is the field gamma concentration is built on and the field
    most likely to be missing: it is published once a day by OCC and arrives
    late, and yfinance surfaces it as NaN when it has nothing. A NaN that became
    a zero silently would make a name look like it had no optionality at all, so
    rows without usable open interest are dropped here and counted by the
    caller rather than carried as zeros.
    """
    out: list[OptionContract] = []
    if "strike" not in frame:
        return out
    has_oi = "openInterest" in frame
    has_iv = "impliedVolatility" in frame
    for row in frame.itertuples(index=False):
        try:
            strike = float(getattr(row, "strike"))
            oi = float(getattr(row, "openInterest")) if has_oi else 0.0
            iv = float(getattr(row, "impliedVolatility")) if has_iv else 0.0
        except (TypeError, ValueError):
            continue
        # NaN fails every comparison with itself; this is the cheap test.
        if strike != strike or oi != oi or iv != iv:
            continue
        if strike <= 0 or oi <= 0 or iv <= 0:
            continue
        out.append(OptionContract(expiry=expiry, side=side, strike=strike,
                                  open_interest=int(oi), implied_volatility=iv))
    return out

# ---------------------------------------------------------------- cache
#
# Yahoo rate-limits a per-ticker scrape long before two thousand names are
# through it, and the failures are individually harmless and collectively
# fatal: the roadmap simply empties. Storing what arrives means a throttled
# night costs the names it missed rather than all of them.

# How long a stored date is trusted before it is looked up again. Companies
# announce a quarter ahead and rarely move it, so a week is generous and keeps
# the nightly request count low enough that Yahoo mostly answers.
FRESH_DAYS = 7


def store_dates(conn, by_symbol: dict[str, list]) -> int:
    """Keep what was fetched. Returns rows written."""
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    written = 0
    for symbol, events in by_symbol.items():
        for event in events:
            conn.execute(
                "INSERT OR REPLACE INTO earnings_dates"
                "(symbol, date, confirmed, fetched_at) VALUES (?,?,?,?)",
                (symbol.upper(), event.date.isoformat(), event.confirmed, now))
            written += 1
    conn.commit()
    return written


def stale_symbols(conn, symbols, fresh_days: int = FRESH_DAYS) -> list[str]:
    """The names worth asking about tonight.

    A symbol with a stored date fetched inside the window is skipped, which is
    what keeps the request count under Yahoo's patience. Everything else — never
    fetched, or fetched long enough ago that the date may have moved — is asked
    for.
    """
    cutoff = (dt.datetime.now(dt.timezone.utc)
              - dt.timedelta(days=fresh_days)).isoformat(timespec="seconds")
    fresh = {r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM earnings_dates WHERE fetched_at >= ?",
        (cutoff,))}
    return [s for s in symbols if s.upper() not in fresh]


def load_dates(conn, symbols, as_of: dt.date) -> dict[str, list[EarningsEvent]]:
    """Everything stored for these names that has not already happened."""
    wanted = {s.upper() for s in symbols}
    out: dict[str, list[EarningsEvent]] = {}
    for row in conn.execute(
            "SELECT symbol, date, confirmed FROM earnings_dates"
            " WHERE date >= ? ORDER BY date", (as_of.isoformat(),)):
        symbol = row[0]
        if symbol not in wanted:
            continue
        try:
            day = dt.date.fromisoformat(row[1])
        except (TypeError, ValueError):
            continue
        out.setdefault(symbol, []).append(EarningsEvent(symbol, day, row[2]))
    return out
