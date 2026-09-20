"""A delayed price for the names currently on a screen.

The site is an end-of-day product and this does not change that. A base does
not form during a session, relative strength is a ranking over months, and
open interest is published once a day by OCC — recomputing any of that
intraday would be inventing precision. What genuinely moves between the close
and now is where price sits against a pivot, which is the one question a
reader has during the session and the one thing a nightly file cannot answer.

So this is deliberately small: one number per name, for the names already on
a screen, written to its own file. Nothing here feeds the detectors, and the
figures it writes are never mixed into the nightly tree — a delayed quote and
a settled close are different things and the page says which it is showing.
"""
from __future__ import annotations

import datetime as dt
import time

from catalysts import cboe

#: How many names one sweep will ask about. The cap has to leave the job
#: finishing well inside its own cadence: at roughly half a second a name it
#: is a few minutes, and a run still going when the next one starts is a run
#: that never publishes.
MAX_SYMBOLS = 400


#: How long one sweep may spend before it stops and publishes what it has.
#: The job it runs in has its own timeout, and being killed by that means
#: publishing nothing — the first paced run was cut off holding four hundred
#: perfectly good quotes. Stopping early with a partial file is strictly
#: better, and because the names are in priority order the ones dropped are
#: the ones furthest from mattering.
TIME_BUDGET_SECONDS = 8 * 60


def collect(symbols, notice=None) -> dict:
    """Fetch a delayed quote per symbol. Returns the published payload.

    `symbols` is taken in the order given and truncated, so the caller decides
    who matters. That ordering is the whole design: the first sweep asked
    alphabetically, which is a ranking by nothing, and spent its budget on the
    letter A while the names actually near a breakout sat past the cut.
    """
    # Reset per call: these counts describe this sweep, and a process that
    # fetched chains earlier would otherwise fold its own tally into them.
    cboe.OUTCOMES.clear()
    seen: set[str] = set()
    wanted: list[str] = []
    for symbol in symbols:
        upper = str(symbol).upper()
        if upper in seen:
            continue
        seen.add(upper)
        wanted.append(upper)
        if len(wanted) >= MAX_SYMBOLS:
            break
    rows: dict[str, dict] = {}
    asked = 0
    started = time.monotonic()
    ran_out = False
    for symbol in wanted:
        if time.monotonic() - started > TIME_BUDGET_SECONDS:
            ran_out = True
            break
        asked += 1
        if notice and asked % 100 == 0:
            notice(f"quotes: {asked:,}/{len(wanted):,} asked, {len(rows):,} answered, "
                   f"{time.monotonic() - started:.0f}s elapsed")
        found = cboe.quote(symbol)
        if found is not None:
            rows[symbol] = found

    if ran_out and notice:
        notice(f"quotes: stopped at {asked:,} of {len(wanted):,} after "
               f"{TIME_BUDGET_SECONDS}s and published what was in hand. The "
               f"names left out are the ones furthest from their pivot.")

    if notice:
        # Always, not only on failure. A hit rate that quietly slides from
        # ninety per cent to twelve is exactly what happened the first time
        # this ran, and a bare success count cannot show it.
        outcomes = ", ".join(f"{k} {v:,}" for k, v in
                             sorted(cboe.OUTCOMES.items(), key=lambda kv: -kv[1]))
        notice(f"quotes: outcomes — {outcomes or 'none recorded'}")
        if rows:
            share = 100.0 * len(rows) / max(1, len(wanted))
            notice(f"quotes: {len(rows):,} of {len(wanted):,} names answered "
                   f"({share:.0f}%).")
        else:
            # Loud for the usual reason: an empty quotes file and a market that
            # has not moved look identical from the outside.
            notice(f"quotes: asked about {len(wanted):,} names and NONE "
                   f"answered. The intraday prices will be absent and the "
                   f"pages will fall back to the closing figures.")

    now = dt.datetime.now(dt.timezone.utc)
    return {
        "fetched_at": now.isoformat(timespec="seconds"),
        "count": len(rows),
        "asked": asked,
        "wanted": len(wanted),
        # True when the clock stopped the sweep rather than the list running
        # out, so a short file can be told from a quiet market.
        "truncated": ran_out,
        "source": "cboe-delayed",
        # Said once, here, so every surface that reads this file has to carry
        # it rather than quietly presenting delayed prices as live ones.
        "note": ("Delayed by roughly fifteen minutes. The screens themselves "
                 "are end-of-day; this is only the price beside them."),
        "quotes": rows,
    }
