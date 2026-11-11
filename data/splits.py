"""Apply stock splits to the stored price history.

Bars are fetched one session at a time and kept. The provider adjusts each
response for the splits it knows about on the day it is asked, so a bar
fetched before a split is at the pre-split price and stays there: nothing
went back for it. Every stock or fund that split after its history was cached
carried a false cliff at the split date, through its chart, its 52-week
range, its relative strength and every pattern that crossed it. ITA read 64%
behind the market at every window in 2026-11 for exactly this reason.

Each night this asks for the splits executed since the last check (the whole
stored history the first time) and, for each one it has not handled, looks at
the stored bars either side of the execution date:

  the price stepped by about the split ratio   the bars before it are
                                               unadjusted: multiply their
                                               prices by the ratio and divide
                                               their volume by it
  the price did not step                       they were fetched after the
                                               split and are already right
  the ratio is under 3-for-2                   a step that small cannot be
                                               told from an ordinary day, so
                                               it is left alone and recorded

The check against the bars is what makes this safe to run over history that
is partly adjusted and partly not, and safe to run twice. Every split is
recorded once handled, with what was done.

The step is looked for at the execution date and at the session before it.
A night's bar is fetched after midnight, and by then the provider has
already applied a split that executes that morning: so the last session
before a split is usually stored at the post-split price, and the cliff sits
one session earlier than the date the split carries. ITA's 3-for-1 was listed
for 2026-11-05 and its stored bars stepped between 11-03 and 11-04. The first
version looked only at the listed date, saw no step there, and recorded the
split as already right.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import sqlite3

from data import store

log = logging.getLogger(__name__)

CHECKED_KEY = "splits.checked_through"
# Splits are sometimes registered a few days late; re-ask this far back each
# night. The applied table stops any being handled twice.
OVERLAP_DAYS = 10
MAX_PAGES = 40
# Below 3-for-2 a split's step is inside the range of an ordinary session.
MIN_LOG_FACTOR = math.log(1.5)
# How many sessions before the execution date the step may sit.
SESSIONS_EARLY = 1
# Bumped when the judging changes, so splits an older rule called already
# right are judged again. Splits that were adjusted are never judged twice.
JUDGE_KEY = "splits.judge_version"
JUDGE_VERSION = "2"


def fetch(adapter, since: dt.date, until: dt.date) -> list[dict]:
    """Every split executed in the window: {symbol, date, factor}."""
    rows: list[dict] = []
    payload = adapter._get("/v3/reference/splits", {                       # noqa: SLF001
        "execution_date.gte": since.isoformat(),
        "execution_date.lte": until.isoformat(), "limit": 1000,
        "order": "asc", "sort": "execution_date"})
    for _ in range(MAX_PAGES):
        for row in payload.get("results") or []:
            try:
                split_from, split_to = float(row["split_from"]), float(row["split_to"])
                if split_from <= 0 or split_to <= 0:
                    continue
                rows.append({"symbol": str(row["ticker"]).upper(),
                             "date": dt.date.fromisoformat(row["execution_date"]),
                             # 3-for-1 is split_from 1, split_to 3: old prices x 1/3.
                             "factor": split_from / split_to})
            except (KeyError, TypeError, ValueError):
                continue
        nxt = payload.get("next_url")
        if not nxt:
            break
        payload = adapter._get(nxt)                                        # noqa: SLF001
    return rows


def judge(conn: sqlite3.Connection, symbol: str, date: dt.date,
          factor: float) -> tuple[str | None, str | None]:
    """What a split calls for, from the stored bars around it.

    Returns the outcome and, when the bars need adjusting, the date of the
    first session already at the post-split price: everything before it is
    adjusted. The outcome is None when the session on or after the execution
    date is not stored yet: there is nothing to compare, so the split is left
    for tomorrow.
    """
    before = [(r[0], r[1]) for r in conn.execute(
        "SELECT date, close FROM bars WHERE symbol=? AND date<? ORDER BY date DESC LIMIT ?",
        (symbol, date.isoformat(), SESSIONS_EARLY + 1))][::-1]
    if not before or not before[-1][1] or before[-1][1] <= 0:
        return "no_bars", None
    after = conn.execute(
        "SELECT date, close FROM bars WHERE symbol=? AND date>=? ORDER BY date LIMIT 1",
        (symbol, date.isoformat())).fetchone()
    if after is None or not after[1] or after[1] <= 0:
        return None, None
    if abs(math.log(factor)) < MIN_LOG_FACTOR:
        return "too_small", None
    # Each pair of neighbouring sessions from the one before the execution
    # date up to it; the step, if the bars were never adjusted, is at one.
    run = [row for row in before if row[1] and row[1] > 0] + [(after[0], after[1])]
    want = math.log(factor)
    best: tuple[float, str] | None = None
    for (_, a), (day, b) in zip(run, run[1:]):
        step = math.log(b / a)
        # Nearer the split's step than no step at all.
        if abs(step - want) < abs(step) and (best is None or abs(step - want) < best[0]):
            best = (abs(step - want), day)
    return ("adjusted", best[1]) if best else ("already_adjusted", None)


def apply(conn: sqlite3.Connection, adapter, as_of: dt.date, dry_run: bool = False,
          notice=None) -> dict:
    """Reconcile every unhandled split against the stored bars."""
    first = conn.execute("SELECT MIN(date) FROM bars").fetchone()[0]
    if not first:
        return {"asked": 0, "adjusted": []}
    checked = store.get_kv(conn, CHECKED_KEY, "")
    # A change to the judging re-asks for the whole history and judges again
    # every split the old rule called already right.
    rejudge = store.get_kv(conn, JUDGE_KEY, "") != JUDGE_VERSION
    since = (dt.date.fromisoformat(checked) - dt.timedelta(days=OVERLAP_DAYS)
             if checked and not rejudge else dt.date.fromisoformat(first))
    rows = fetch(adapter, since, as_of)
    done = {(r[0], r[1]) for r in conn.execute(
        "SELECT symbol, execution_date, outcome FROM splits_applied")
            if not (rejudge and r[2] == "already_adjusted")}
    counts = {"adjusted": 0, "already_adjusted": 0, "too_small": 0, "no_bars": 0, "pending": 0}
    adjusted: list[dict] = []
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for row in sorted(rows, key=lambda r: (r["date"], r["symbol"])):
        symbol, date, factor = row["symbol"], row["date"], row["factor"]
        if (symbol, date.isoformat()) in done:
            continue
        outcome, cutoff = judge(conn, symbol, date, factor)
        if outcome is None:
            counts["pending"] += 1
            continue
        counts[outcome] += 1
        touched = 0
        if outcome == "adjusted":
            if not dry_run:
                cur = conn.execute(
                    "UPDATE bars SET open=open*?, high=high*?, low=low*?, close=close*?,"
                    " volume=volume/? WHERE symbol=? AND date<?",
                    (factor, factor, factor, factor, factor, symbol, cutoff))
                touched = cur.rowcount
            adjusted.append({"symbol": symbol, "date": date.isoformat(),
                             "factor": round(factor, 6), "bars": touched,
                             "from": cutoff})
        if not dry_run and outcome != "no_bars":
            # A split with no bars before it is not recorded: the symbol may be
            # backfilled later, and then it needs judging.
            conn.execute(
                "INSERT OR REPLACE INTO splits_applied"
                "(symbol, execution_date, factor, outcome, bars, applied_at)"
                " VALUES (?,?,?,?,?,?)",
                (symbol, date.isoformat(), factor, outcome, touched, now))
    if not dry_run:
        store.set_kv(conn, CHECKED_KEY, as_of.isoformat())
        store.set_kv(conn, JUDGE_KEY, JUDGE_VERSION)
        conn.commit()
    if notice:
        notice(f"Splits since {since}: {len(rows):,} listed; "
               f"{counts['adjusted']} adjusted, {counts['already_adjusted']} already right, "
               f"{counts['too_small']} too small to verify, {counts['pending']} not settled yet.")
        # Newest first: the splits a reader is most likely looking for are the
        # recent ones, and the list is cut at forty.
        for a in sorted(adjusted, key=lambda r: r["date"], reverse=True)[:40]:
            notice(f"  split {a['symbol']} {a['date']} x{a['factor']:g}"
                   + (f", bars before {a['from']}" if a["from"] != a["date"] else "")
                   + (f" ({a['bars']:,} bars)" if not dry_run else " (would adjust)"))
    return {"asked": len(rows), "since": since.isoformat(), **counts, "adjusted": adjusted}
