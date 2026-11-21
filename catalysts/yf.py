"""yfinance-backed earnings dates and option chains.

yfinance scrapes an undocumented endpoint. It breaks without notice and rate
limits opaquely, so every call here degrades to empty rather than raising: a
missing earnings date costs a badge, a failed nightly run costs the whole site.
"""
from __future__ import annotations

import collections
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


def reported_dates(conn, symbols, as_of: dt.date) -> dict[str, list[dt.date]]:
    """Report dates that have happened, per symbol, newest first.

    Only rows Yahoo returned with a reported EPS. Its future rows are
    estimates, and a past date that was only ever estimated is a day the
    company may not have reported at all -- measuring the move across it
    would attribute an ordinary week to earnings.
    """
    wanted = {s.upper() for s in symbols}
    out: dict[str, list[dt.date]] = {}
    for row in conn.execute(
            "SELECT symbol, date FROM earnings_dates"
            " WHERE date < ? AND confirmed = 'confirmed' ORDER BY date DESC",
            (as_of.isoformat(),)):
        if row[0] not in wanted:
            continue
        try:
            out.setdefault(row[0], []).append(dt.date.fromisoformat(row[1]))
        except (TypeError, ValueError):
            continue
    return out


# ------------------------------------------------------------------ quotes

#: The endpoint Yahoo's own pages read a watchlist from. It answers for a few
#: hundred names in one request, which is the whole reason to use it: a probe
#: from the runner got 400 of 400 in under half a second, where one request a
#: name against the previous source took six minutes on a good day.
QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
QUOTE_BATCH = 200

#: What happened to every name asked in this process, by how it was answered.
QUOTE_OUTCOMES: "collections.Counter[str]" = collections.Counter()

_NEW_YORK = None


def _new_york():
    global _NEW_YORK                                # noqa: PLW0603
    if _NEW_YORK is None:
        from zoneinfo import ZoneInfo               # noqa: PLC0415
        _NEW_YORK = ZoneInfo("America/New_York")
    return _NEW_YORK


def yahoo_symbol(symbol: str) -> str:
    """Yahoo's spelling of a ticker. Class shares take a dash: BRK.B is BRK-B."""
    return symbol.strip().upper().replace(".", "-")


def _positive(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number and number > 0 else 0.0


def quote_row(last, previous, traded_at=None) -> dict | None:
    """One published quote, in the shape every reader of the file expects."""
    last = _positive(last)
    if last <= 0:
        return None
    previous = _positive(previous)
    at = None
    stamp = _positive(traded_at)
    if stamp:
        # New York wall time without an offset, because that is what the file
        # has always carried and what the page prints as it stands.
        at = (dt.datetime.fromtimestamp(stamp, dt.timezone.utc)
              .astimezone(_new_york()).replace(tzinfo=None)
              .isoformat(timespec="seconds"))
    return {
        "last": round(last, 4),
        "prev_close": round(previous, 4) if previous else None,
        # None rather than zero with nothing to compare against: unknown must
        # not read as unchanged.
        "change_pct": round(100.0 * (last / previous - 1.0), 2) if previous else None,
        "at": at,
    }


def _quotes_from_endpoint(yf, symbols: Sequence[str]) -> dict[str, dict]:
    """The quote endpoint, two hundred names a request."""
    from yfinance.data import YfData                # noqa: PLC0415 - optional
    data = YfData()
    spelled = {yahoo_symbol(s): s for s in symbols}
    asked = list(spelled)
    out: dict[str, dict] = {}
    for start in range(0, len(asked), QUOTE_BATCH):
        batch = asked[start:start + QUOTE_BATCH]
        try:
            response = data.get(QUOTE_URL, params={"symbols": ",".join(batch)})
            if response.status_code != 200:
                QUOTE_OUTCOMES[f"batch_http_{response.status_code}"] += 1
                continue
            rows = (response.json().get("quoteResponse") or {}).get("result") or []
        except Exception as exc:                    # noqa: BLE001
            QUOTE_OUTCOMES["batch_error"] += 1
            log.debug("yahoo quote batch failed: %s", exc)
            continue
        for row in rows:
            symbol = spelled.get(str(row.get("symbol") or "").upper())
            if not symbol:
                continue
            found = quote_row(row.get("regularMarketPrice"),
                              row.get("regularMarketPreviousClose"),
                              row.get("regularMarketTime"))
            if found is not None:
                out[symbol] = found
    return out


def _quotes_from_download(yf, symbols: Sequence[str]) -> dict[str, dict]:
    """The library's own batch download: the last two daily closes.

    Slower and with no trade time, but it is the library's public surface. The
    endpoint above is reached through its internals, which have moved before;
    when they move again this still answers.
    """
    spelled = {yahoo_symbol(s): s for s in symbols}
    out: dict[str, dict] = {}
    try:
        frame = yf.download(list(spelled), period="5d", interval="1d", threads=True,
                            progress=False, auto_adjust=False, group_by="ticker")
    except Exception as exc:                        # noqa: BLE001
        QUOTE_OUTCOMES["download_error"] += 1
        log.debug("yahoo download failed: %s", exc)
        return out
    for yahoo, symbol in spelled.items():
        try:
            closes = [float(v) for v in frame[yahoo]["Close"].dropna().tolist()]
        except Exception:                           # noqa: BLE001
            continue
        if not closes:
            continue
        found = quote_row(closes[-1], closes[-2] if len(closes) > 1 else None)
        if found is not None:
            out[symbol] = found
    return out


def quotes(symbols: Sequence[str]) -> dict[str, dict]:
    """A delayed price for many companies at once. Missing names are absent.

    Never raises: an empty answer sends the caller to its next source.
    """
    QUOTE_OUTCOMES.clear()
    wanted = list(dict.fromkeys(str(s).upper() for s in symbols if s))
    yf = _yf()
    if yf is None or not wanted:
        return {}
    out: dict[str, dict] = {}
    try:
        out = _quotes_from_endpoint(yf, wanted)
    except Exception as exc:                        # noqa: BLE001
        QUOTE_OUTCOMES["endpoint_unavailable"] += 1
        log.debug("yahoo quote endpoint unavailable: %s", exc)
    QUOTE_OUTCOMES["endpoint"] += len(out)
    missing = [s for s in wanted if s not in out]
    # Only when a request failed or a real share is missing. A handful of
    # names Yahoo does not carry is ordinary and not worth a second pass.
    failed = any(key.startswith(("batch_", "endpoint_unavailable"))
                 for key in QUOTE_OUTCOMES)
    if missing and (failed or len(missing) > max(5, len(wanted) // 20)):
        rest = _quotes_from_download(yf, missing)
        QUOTE_OUTCOMES["download"] += len(rest)
        out.update(rest)
    QUOTE_OUTCOMES["missing"] += len(wanted) - len(out)
    return out
