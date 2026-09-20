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

from catalysts import cboe

#: Names on no screen are not fetched. The file exists to answer "is this
#: setup breaking out right now", and a stock that is not on a screen has
#: nothing for the answer to be about.
MAX_SYMBOLS = 900


def collect(symbols, notice=None) -> dict:
    """Fetch a delayed quote per symbol. Returns the published payload."""
    wanted = sorted({s.upper() for s in symbols})[:MAX_SYMBOLS]
    rows: dict[str, dict] = {}
    asked = 0
    for symbol in wanted:
        asked += 1
        if notice and asked % 200 == 0:
            notice(f"quotes: {asked:,}/{len(wanted):,} asked, {len(rows):,} answered")
        found = cboe.quote(symbol)
        if found is not None:
            rows[symbol] = found

    if notice:
        if rows:
            notice(f"quotes: {len(rows):,} of {len(wanted):,} names answered.")
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
        "asked": len(wanted),
        "source": "cboe-delayed",
        # Said once, here, so every surface that reads this file has to carry
        # it rather than quietly presenting delayed prices as live ones.
        "note": ("Delayed by roughly fifteen minutes. The screens themselves "
                 "are end-of-day; this is only the price beside them."),
        "quotes": rows,
    }
