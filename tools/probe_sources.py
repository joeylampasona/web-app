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

import json
import os
import sys
import urllib.error
import urllib.request

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
    print("1. SHARE COUNTS — why the multi-class mega caps are absent")
    print(RULE)
    # CIKs are public identifiers, not configuration. Hard-coded here because
    # this is a one-off diagnostic, not a code path the site depends on.
    subjects = {
        "META": "0001326801", "GOOGL": "0001652044",
        "BRK.B": "0001067983", "AAPL": "0000320193", "NVDA": "0001045810",
    }
    concept = ("https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}"
               "/dei/EntityCommonStockSharesOutstanding.json")
    for symbol, cik in subjects.items():
        print(f"\n{symbol}  (CIK {cik})")
        try:
            payload = _get(concept.format(cik=cik), agent)
        except urllib.error.HTTPError as exc:
            print(f"   companyconcept -> HTTP {exc.code}")
            payload = None
        except Exception as exc:                      # noqa: BLE001
            print(f"   companyconcept -> {type(exc).__name__}: {exc}")
            payload = None

        if payload is not None:
            units = payload.get("units", {}).get("shares", [])
            print(f"   companyconcept -> {len(units)} entries in units['shares']")
            for entry in sorted(units, key=lambda e: e.get("end", ""))[-4:]:
                print(f"      end={entry.get('end')} val={entry.get('val'):,.0f} "
                      f"form={entry.get('form')} accn={entry.get('accn')} "
                      f"frame={entry.get('frame')}")
            if not units:
                print("      ^ EMPTY — this is the gate the company falls through.")

        # What the whole-company facts file says, which is where per-class
        # numbers live if they live anywhere.
        try:
            facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", agent)
        except Exception as exc:                      # noqa: BLE001
            print(f"   companyfacts -> {type(exc).__name__}: {exc}")
            continue
        dei = (facts.get("facts", {}).get("dei", {})
               .get("EntityCommonStockSharesOutstanding", {})
               .get("units", {}).get("shares", []))
        print(f"   companyfacts dei -> {len(dei)} entries")
        for entry in sorted(dei, key=lambda e: e.get("end", ""))[-6:]:
            print(f"      end={entry.get('end')} val={entry.get('val'):,.0f} "
                  f"form={entry.get('form')} accn={entry.get('accn')}")
        gaap = facts.get("facts", {}).get("us-gaap", {})
        for name in ("CommonStockSharesOutstanding", "CommonStockSharesIssued",
                     "WeightedAverageNumberOfSharesOutstandingBasic"):
            rows = gaap.get(name, {}).get("units", {}).get("shares", [])
            if not rows:
                continue
            latest = max(rows, key=lambda e: e.get("end", ""))
            print(f"   us-gaap {name}: {len(rows)} entries, latest "
                  f"end={latest.get('end')} val={latest.get('val'):,.0f}")


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
    print()
    print(RULE)
    print("Probe complete. Nothing was written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
