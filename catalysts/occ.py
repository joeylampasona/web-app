"""Open interest from the clearing house.

OCC clears every listed option in the United States, and publishes, free and
without a key, one file per underlying: every listed series with the open
interest it cleared. That is the figure every other source is repeating a day
late, and it covers the whole book — every expiry, every strike — which is
what gamma concentration is a statement about.

It carries no prices and no implied volatility, so it is half a chain. The
other half comes from Yahoo; see catalysts/chains.py for how they are joined.

This is here because on 2026-11-19 Cboe began refusing every request that did
not come from a browser on its own site, and the fallback, Yahoo alone, shows
open interest on a fraction of the book. Market Desk measured the same thing
the same week and reached for the same file.
"""
from __future__ import annotations

import collections
import datetime as dt
import logging
import re
import time

import requests

log = logging.getLogger(__name__)

URL = "https://marketdata.theocc.com/series-search"
TIMEOUT = 45
AGENT = "tape-research"

# A file a name, several hundred names a night. Slower than it needs to be on
# purpose: this is a public courtesy from a clearing house, not a feed.
PAUSE = 0.15

# How many names in a row may go unanswered before the rest are not asked.
# Same reasoning as Cboe's: a host that has started saying no is not going to
# be talked round by asking four hundred more times.
FAILURES_BEFORE_STANDING_DOWN = 8

# What the body says, lower-cased, when OCC lists nothing for the symbol.
NOTHING_LISTED = "no data exists"

#: What happened to every request made in this process.
OUTCOMES: "collections.Counter[str]" = collections.Counter()

_failed_in_a_row = 0

#: (expiry, "call" | "put", strike) -> contracts outstanding.
Book = dict[tuple[dt.date, str, float], int]


def standing_down() -> bool:
    return _failed_in_a_row >= FAILURES_BEFORE_STANDING_DOWN


def reset() -> None:
    """Forget the failures. For a new sweep in the same process, and tests."""
    global _failed_in_a_row                        # noqa: PLW0603
    _failed_in_a_row = 0


def spelling(symbol: str) -> str:
    """OCC's spelling of a ticker. Class shares lose the dot: BRK.B is BRKB."""
    return re.sub(r"[.\-/ ]", "", (symbol or "").strip().upper())


def parse(text: str) -> Book | None:
    """The series file as a book, or None when the text is not the file.

    Its rows, tab separated with runs of empty cells: root, year, month, day,
    the strike's whole part, its thousandths, "C P", call open interest, put
    open interest, position limit.

    A root with a digit in it (NVDA1) is an adjusted series left behind by a
    split or a merger. It delivers something other than a hundred shares, so
    its open interest is not this company's gamma and it is left out.

    Returning None for a page that is not the file matters: a block page
    answers 200 as readily as the file does, and an empty book would read as
    "this company has no listed options".
    """
    lines = (text or "").splitlines()
    header = next((i for i, line in enumerate(lines)
                   if line.startswith("ProductSymbol")), None)
    if header is None:
        return None
    book: Book = {}
    for line in lines[header + 1:]:
        cells = [c.strip() for c in re.split(r"\t+", line.strip())]
        if len(cells) < 9 or not re.fullmatch(r"[A-Z]+", cells[0]):
            continue
        try:
            expiry = dt.date(int(cells[1]), int(cells[2]), int(cells[3]))
            strike = int(cells[4]) + int(cells[5]) / 1000.0
            calls, puts = int(float(cells[7])), int(float(cells[8]))
        except ValueError:
            continue
        if strike <= 0:
            continue
        # Summed, not assigned: two plain roots on one underlying are rare
        # for a company and both are its book when it happens.
        book[(expiry, "call", strike)] = book.get((expiry, "call", strike), 0) + calls
        book[(expiry, "put", strike)] = book.get((expiry, "put", strike), 0) + puts
    return book


def open_interest(symbol: str) -> Book | None:
    """The cleared book for one underlying.

    Three answers, and the caller needs all three kept apart:
      a book    it answered and the company has listed series
      {}        it answered and lists nothing for this symbol
      None      it did not answer, so nothing is known either way
    """
    global _failed_in_a_row                        # noqa: PLW0603
    if standing_down():
        OUTCOMES["not_asked"] += 1
        return None
    headers = {"User-Agent": AGENT, "Accept": "text/plain, */*"}
    params = {"symbolType": "U", "symbol": spelling(symbol)}
    for attempt in (1, 2):
        try:
            response = requests.get(URL, params=params, headers=headers,
                                    timeout=TIMEOUT)
            time.sleep(PAUSE)
            code = response.status_code
            if code == 200:
                book = parse(response.text)
                if book is None:
                    # Answered, with something that is not the file. For a
                    # company with no listed options, and for a symbol it has
                    # never heard of, OCC answers 200 with one line: "No data
                    # exists for WINA symbol". A block page would also be a
                    # 200 that is not the file, so it is read by what it says.
                    if NOTHING_LISTED in response.text.lower():
                        OUTCOMES["unknown_symbol"] += 1
                        _failed_in_a_row = 0
                        return {}
                    OUTCOMES["not_the_file"] += 1
                    _failed_in_a_row += 1
                    return None
                OUTCOMES["ok" if book else "empty"] += 1
                _failed_in_a_row = 0
                return book
            if code in (400, 404):
                OUTCOMES["unknown_symbol"] += 1
                _failed_in_a_row = 0
                return {}
            OUTCOMES[f"http_{code}"] += 1
            log.debug("occ %s: HTTP %s", symbol, code)
        except requests.RequestException as exc:
            OUTCOMES["error"] += 1
            log.debug("occ %s: %s", symbol, exc)
        if attempt == 1:
            time.sleep(2.0)
    _failed_in_a_row += 1
    return None
