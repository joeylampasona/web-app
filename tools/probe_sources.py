"""Ask the outside world what it actually returns, and print it.

Two sections of the site are empty for reasons that cannot be diagnosed from
a development machine, because the sources involved are not reachable from
one. Rather than guess at their shapes and ship an adapter written against
the guess, this probe runs where the nightly runs and reports what comes
back. It writes nothing and changes nothing.

  1. Share counts. Meta, Alphabet and Berkshire are absent from the universe.
     Every one of them is a multi-class filer, and the suspicion is that the
     dei concept we read is reported per share class for those companies and
     so comes back empty. This prints the raw response so the suspicion is
     either confirmed or discarded.

  2. Option open interest. Gamma has never had a single usable row. Implied
     volatility comes off the same chains in the same pass and works fine, so
     the chains arrive and the open-interest field does not. This prints what
     the field actually contains, and tries one alternative source.

Run it from the repository root. It needs EDGAR_USER_AGENT set, and never
prints it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

import requests

# Run as a script, sys.path[0] is tools/ rather than the repository root, so
# `from data import store` fails and the flag sweep quietly reports that it
# cannot import the pipeline. The root is one level up from this file.
_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

TIMEOUT = 30
RULE = "─" * 68


def _get(url: str, agent: str, as_json: bool = True):
    request = urllib.request.Request(url, headers={
        "User-Agent": agent,
        "Accept": "application/json,text/plain,*/*",
    })
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = response.read()
    return json.loads(raw) if as_json else raw


def probe_shares(agent: str) -> None:
    print(RULE)
    print("1. SHARE COUNTS — why heavily traded names get dropped")
    print(RULE)
    # Driven through data.edgar itself rather than a parallel copy of its
    # logic. The last version of this probe built its own URLs and put the CIK
    # prefix on twice — every company came back 404, including Apple, and the
    # output read as "SEC has nothing for any of these" when what it meant was
    # "this probe cannot spell". A diagnostic that reimplements the thing it is
    # diagnosing is a second thing that can be wrong.
    from data import edgar

    wanted = ["KO", "ABT", "SPGI", "NU", "BE", "BRK.B", "META", "AAPL"]

    session = requests.Session()
    try:
        cik_map = edgar._ticker_to_cik(session)
    except Exception as exc:                          # noqa: BLE001
        print(f"   ticker map unavailable: {exc}")
        return
    print(f"   SEC ticker map: {len(cik_map):,} tickers\n")

    for symbol in wanted:
        tried = edgar._cik_candidates(symbol)
        match = next(((name, cik_map[name]) for name in tried
                      if name in cik_map), None)
        if match is None:
            print(f"{symbol}: no CIK under any of {tried} — this alone drops it")
            continue
        spelling, cik = match
        note = "" if spelling == symbol.upper() else f"  (SEC spells it {spelling})"
        print(f"{symbol}  {cik}{note}")
        found = False

        for taxonomy, concept in edgar._SHARE_CONCEPTS:
            url = (f"https://data.sec.gov/api/xbrl/companyconcept/{cik}"
                   f"/{taxonomy}/{concept}.json")
            try:
                resp = session.get(url, headers={"User-Agent": agent}, timeout=30)
            except Exception as exc:                  # noqa: BLE001
                print(f"   {taxonomy}/{concept} -> {type(exc).__name__}: {exc}")
                continue
            time.sleep(0.15)
            if resp.status_code != 200:
                print(f"   {taxonomy}/{concept} -> HTTP {resp.status_code}")
                continue
            payload = resp.json()
            all_units = payload.get("units", {}) or {}
            units = all_units.get("shares", [])
            newest = max((u for u in units if u.get("end")),
                         key=lambda u: u["end"], default=None)
            if newest is None:
                # "200 with nothing in it" was the answer for four of the six
                # dropped names, and the production code reads one unit key.
                # If the series is filed under another key that is the whole
                # story, so say which keys exist rather than only that ours
                # was empty.
                shapes = {name: len(rows) for name, rows in all_units.items()}
                print(f"   {taxonomy}/{concept} -> 200, units={shapes or '{}'}")
                for name, rows in all_units.items():
                    dated = [r for r in rows if r.get("end")]
                    if not dated:
                        continue
                    latest = max(dated, key=lambda r: r["end"])
                    age = (dt.date.today()
                           - dt.date.fromisoformat(latest["end"])).days
                    print(f"        unit {name!r}: newest {latest['end']} "
                          f"({age}d) val {latest.get('val', 0):,.0f}")
                continue
            age = (dt.date.today() - dt.date.fromisoformat(newest["end"])).days
            verdict = "USABLE" if age <= edgar.SHARES_MAX_AGE_DAYS else \
                      f"TOO OLD (limit {edgar.SHARES_MAX_AGE_DAYS}d)"
            print(f"   {taxonomy}/{concept} -> {len(units)} entries, "
                  f"newest {newest['end']} ({age}d) "
                  f"val {newest.get('val', 0):,.0f} — {verdict}")
            if age <= edgar.SHARES_MAX_AGE_DAYS:
                found = True
                break
        else:
            _sweep_companyfacts(session, cik, agent,
                                edgar.SHARES_MAX_AGE_DAYS)
        print()


def _sweep_companyfacts(session, cik: str, agent: str,
                        max_age: int) -> None:
    """Every share-shaped series this company files, newest first.

    Called only for the companies the fixed list of concepts failed. The point
    is to stop guessing concept names: if a recent share count exists anywhere
    in this filer's facts, this prints its concept, and the fallback can then
    be written against what companies actually tag rather than what they are
    supposed to tag.
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/{cik}.json"
    try:
        resp = session.get(url, headers={"User-Agent": agent}, timeout=60)
    except Exception as exc:                          # noqa: BLE001
        print(f"   companyfacts -> {type(exc).__name__}: {exc}")
        return
    time.sleep(0.15)
    if resp.status_code != 200:
        print(f"   companyfacts -> HTTP {resp.status_code}")
        return

    today = dt.date.today()
    hits = []
    for taxonomy, concepts in (resp.json().get("facts", {}) or {}).items():
        for name, body in concepts.items():
            for unit, rows in (body.get("units", {}) or {}).items():
                if "share" not in unit.lower():
                    continue
                dated = [r for r in rows if r.get("end") and (r.get("val") or 0) > 0]
                if not dated:
                    continue
                latest = max(dated, key=lambda r: r["end"])
                age = (today - dt.date.fromisoformat(latest["end"])).days
                hits.append((age, taxonomy, name, unit, latest))
    hits.sort()
    if not hits:
        print("   companyfacts -> no share-unit series at all")
        return
    print(f"   companyfacts -> {len(hits)} share-unit series; freshest:")
    for age, taxonomy, name, unit, latest in hits[:6]:
        flag = "USABLE" if age <= max_age else "too old"
        print(f"        {taxonomy}/{name} [{unit}] {latest['end']} "
              f"({age}d) val {latest.get('val', 0):,.0f} — {flag}")


def probe_open_interest(agent: str) -> None:
    print()
    print(RULE)
    print("2. OPEN INTEREST — why gamma has never had a row")
    print(RULE)
    symbols = ["AAPL", "NVDA", "SPY"]

    print("\n-- Yahoo, via yfinance (the source in use) --")
    try:
        import yfinance as yf
    except Exception as exc:                          # noqa: BLE001
        print(f"   yfinance unavailable: {exc}")
    else:
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                expiries = ticker.options
                if not expiries:
                    print(f"   {symbol}: no expiries returned")
                    continue
                chain = ticker.option_chain(expiries[0])
                frame = chain.calls
                print(f"   {symbol}: {len(expiries)} expiries, "
                      f"{len(frame)} calls on {expiries[0]}")
                if "openInterest" not in frame:
                    print("      NO openInterest COLUMN")
                else:
                    series = frame["openInterest"]
                    print(f"      openInterest: non-null {series.notna().sum()}"
                          f"/{len(series)}, sum {series.fillna(0).sum():,.0f}, "
                          f"first five {list(series.head(5))}")
                if "impliedVolatility" in frame:
                    iv = frame["impliedVolatility"]
                    print(f"      impliedVolatility: non-null {iv.notna().sum()}"
                          f"/{len(iv)}  (this is the field that DOES work)")
            except Exception as exc:                  # noqa: BLE001
                print(f"   {symbol}: {type(exc).__name__}: {exc}")

    print("\n-- Yahoo fast_info spot (gamma bails when this is 0) --")
    try:
        import yfinance as yf
    except Exception:                                 # noqa: BLE001
        pass
    else:
        for symbol in symbols:
            try:
                info = yf.Ticker(symbol).fast_info
                raw = info.get("last_price")
                print(f"   {symbol}: type={type(info).__name__} "
                      f"last_price={raw!r} -> float {float(raw or 0.0)}")
                for key in ("lastPrice", "regularMarketPrice", "previousClose"):
                    try:
                        print(f"      {key}: {info.get(key)!r}")
                    except Exception as exc:          # noqa: BLE001
                        print(f"      {key}: {type(exc).__name__}")
            except Exception as exc:                  # noqa: BLE001
                print(f"   {symbol}: {type(exc).__name__}: {exc}")

    print("\n-- Cboe delayed quotes (candidate replacement, no key needed) --")
    for symbol in symbols:
        url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"
        try:
            payload = _get(url, agent)
        except urllib.error.HTTPError as exc:
            print(f"   {symbol}: HTTP {exc.code}")
            continue
        except Exception as exc:                      # noqa: BLE001
            print(f"   {symbol}: {type(exc).__name__}: {exc}")
            continue
        data = payload.get("data") or {}
        options = data.get("options") or []
        print(f"   {symbol}: {len(options)} contracts, "
              f"spot fields {[k for k in data if 'close' in k or 'last' in k]}")
        if options:
            print(f"      keys on one contract: {sorted(options[0])}")
            with_oi = [o for o in options if (o.get("open_interest") or 0) > 0]
            total = sum(o.get("open_interest") or 0 for o in options)
            print(f"      open_interest > 0 on {len(with_oi)}/{len(options)}, "
                  f"total {total:,}")
            sample = options[0]
            print(f"      sample: option={sample.get('option')} "
                  f"oi={sample.get('open_interest')} iv={sample.get('iv')}")


def probe_quote_sources(agent: str) -> None:
    """Candidates for a light intraday quote, one request for many names.

    The nightly is end-of-day and should stay that way — a base does not change
    during a session. What does change is where price sits against a pivot, and
    that needs a cheap delayed quote for a few hundred names, not a second
    market-data pipeline.
    """
    print()
    print(RULE)
    print("4. QUOTE SOURCES — for a delayed intraday price")
    print(RULE)
    symbols = ["AAPL", "NVDA", "MSFT"]

    print("\n-- Stooq light CSV, one symbol --")
    url = "https://stooq.com/q/l/?s=aapl.us&f=sd2t2ohlcvn&h&e=csv"
    try:
        raw = _get(url, agent, as_json=False).decode("utf-8", "replace")
        print("   " + "\n   ".join(raw.strip().splitlines()[:3]))
    except Exception as exc:                          # noqa: BLE001
        print(f"   {type(exc).__name__}: {exc}")

    print("\n-- Stooq light CSV, batched (the thing that matters) --")
    joined = "+".join(f"{s.lower()}.us" for s in symbols)
    url = f"https://stooq.com/q/l/?s={joined}&f=sd2t2ohlcv&h&e=csv"
    try:
        raw = _get(url, agent, as_json=False).decode("utf-8", "replace")
        lines = raw.strip().splitlines()
        print(f"   {len(lines)} lines for {len(symbols)} symbols")
        for line in lines[:5]:
            print("   " + line)
    except Exception as exc:                          # noqa: BLE001
        print(f"   {type(exc).__name__}: {exc}")

    print("\n-- Cboe, is there a quote endpoint lighter than the chain? --")
    for path in ("quotes", "equities"):
        url = f"https://cdn.cboe.com/api/global/delayed_quotes/{path}/AAPL.json"
        try:
            payload = _get(url, agent)
            data = payload.get("data") or {}
            print(f"   /{path}/ -> keys {sorted(data)[:12]}")
        except urllib.error.HTTPError as exc:
            print(f"   /{path}/ -> HTTP {exc.code}")
        except Exception as exc:                      # noqa: BLE001
            print(f"   /{path}/ -> {type(exc).__name__}")


def main() -> int:
    agent = os.environ.get("EDGAR_USER_AGENT", "").strip()
    if not agent:
        print("EDGAR_USER_AGENT is not set. SEC refuses anonymous requests and "
              "Cboe is happier with a named agent. Set it and run again.")
        return 2
    # Never print the agent itself: it is a contact address kept in a secret.
    print(f"Contact agent configured: yes ({len(agent)} characters)\n")
    probe_shares(agent)
    probe_open_interest(agent)
    probe_flag_gates()
    probe_quote_sources(agent)
    print()
    print(RULE)
    print("Probe complete. Nothing was written.")
    return 0


def probe_flag_gates() -> None:
    """How each bull-flag gate cuts the field, on live prices.

    The channel width was chosen off the synthetic fixture, which is 523
    invented names and not a market. This prints the same sweep against
    whatever the database actually holds, so the number can be picked from
    real prices instead.
    """
    print()
    print(RULE)
    print("3. BULL FLAG — what each gate costs, on the live database")
    print(RULE)
    try:
        from data import store
        from patterns import shapes
    except Exception as exc:                          # noqa: BLE001
        print(f"   cannot import the pipeline: {exc}")
        return
    try:
        conn = store.open_db()
        symbols = store.universe_symbols(conn)
        series = {s: b for s, b in store.load_many(conn, symbols).items()
                  if len(b) >= 120}
    except Exception as exc:                          # noqa: BLE001
        print(f"   no usable database here: {exc}")
        return
    if not series:
        print("   the database has no bars — nothing to measure.")
        return
    print(f"   {len(series):,} names with enough history\n")

    spec = dict(max_flag_sessions=7, min_flag_sessions=3, min_pole_pct=10.0,
                max_pole_sessions=5, min_pole_sessions=3, max_retrace=0.50,
                min_pole_volume=1.0, ema_window=20)

    def count(**over):
        kw = dict(spec)
        kw.update(over)
        return sum(1 for bars in series.values() if shapes.find_flag(bars, **kw))

    print("   one gate at a time, channel held open")
    for label, over in (
            ("pole >=10% in 3-5 sessions, flag 3-7",
             dict(max_channel_pct=100.0, min_pole_volume=0.0, ema_window=0)),
            ("+ pole volume >= 1x normal", dict(max_channel_pct=100.0, ema_window=0)),
            ("+ close above the 20-day EMA", dict(max_channel_pct=100.0)),
    ):
        print(f"      {label:40} {count(**over):4d}")

    print()
    print("   then the channel, everything else at spec")
    for width in (3, 4, 5, 6, 8, 10, 12, 15, 20):
        print(f"      pause may wander {width:>2}% high-to-low          "
              f"{count(max_channel_pct=float(width)):4d}")


if __name__ == "__main__":
    sys.exit(main())
