"""Which companies are in the S&P 500.

A tag on a stock's page and a filter on a screen, nothing more. Membership
changes a handful of times a year, so the list is fetched once a week and
kept in the database; a night it cannot be fetched uses the list it has.

The source is the maintained public list at github.com/datasets, which is a
CSV of the current constituents. It is a convenience copy and not S&P's own
publication: S&P does not publish the list freely. A list that comes back
at the wrong size is not believed.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging

import requests

from data import store

log = logging.getLogger(__name__)

URL = ("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
       "main/data/constituents.csv")
KV_KEY = "index.sp500"
AGENT = "tape-research"
TIMEOUT = 30

#: Days before the list is asked for again.
REFRESH_DAYS = 6

#: The index holds about 503 lines for 500 companies. A file far from that
#: is a moved file, an error page or a different list.
PLAUSIBLE = (480, 520)


def parse(text: str) -> list[str]:
    """Tickers from the constituents file, in The Tape's spelling. The file
    writes a share class with a dot, as the price feed does: BRK.B."""
    rows = csv.DictReader(io.StringIO(text or ""))
    out = []
    for row in rows:
        symbol = str(row.get("Symbol") or "").strip().upper().replace("-", ".")
        if symbol:
            out.append(symbol)
    return sorted(set(out))


def refresh(conn, today: dt.date, notice=None) -> dict:
    """Fetch the list when the kept one is old. Never raises; returns what
    happened: {"status", "count", "fetched_on"}."""
    kept = _kept(conn)
    if kept and (today - dt.date.fromisoformat(kept["fetched_on"])).days < REFRESH_DAYS:
        return {"status": "fresh", "count": len(kept["symbols"]),
                "fetched_on": kept["fetched_on"]}
    try:
        response = requests.get(URL, timeout=TIMEOUT, headers={"User-Agent": AGENT})
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")
        symbols = parse(response.text)
        if not PLAUSIBLE[0] <= len(symbols) <= PLAUSIBLE[1]:
            raise ValueError(f"{len(symbols)} names, which is not the S&P 500")
    except (requests.RequestException, ValueError) as exc:
        if notice:
            notice(f"S&P 500 list not refreshed ({exc}); "
                   + (f"using the list from {kept['fetched_on']}." if kept
                      else "no list on file, so no company is tagged."))
        return {"status": "kept" if kept else "none",
                "count": len(kept["symbols"]) if kept else 0,
                "fetched_on": kept["fetched_on"] if kept else None}
    store.set_kv(conn, KV_KEY, json.dumps(
        {"fetched_on": today.isoformat(), "symbols": symbols}, separators=(",", ":")))
    if notice:
        changed = ""
        if kept:
            added = sorted(set(symbols) - set(kept["symbols"]))
            left = sorted(set(kept["symbols"]) - set(symbols))
            if added or left:
                changed = (f" Joined: {', '.join(added) or 'none'}. "
                           f"Left: {', '.join(left) or 'none'}.")
        notice(f"S&P 500 list refreshed: {len(symbols)} lines.{changed}")
    return {"status": "refreshed", "count": len(symbols), "fetched_on": today.isoformat()}


def _kept(conn) -> dict | None:
    try:
        kept = json.loads(store.get_kv(conn, KV_KEY, "") or "null")
        dt.date.fromisoformat(kept["fetched_on"])
        return kept if isinstance(kept.get("symbols"), list) else None
    except (TypeError, ValueError, KeyError):
        return None


def sp500(conn) -> tuple[set[str], str | None]:
    """The members on file and the day they were fetched. An empty set and
    None before the first fetch, which a page must not read as "not in it"."""
    kept = _kept(conn)
    if not kept:
        return set(), None
    return set(kept["symbols"]), kept["fetched_on"]
