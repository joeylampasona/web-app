"""Headlines per ticker, from the price provider's news feed.

Fetched market-wide rather than per ticker. The free tier allows five calls a
minute, so asking about nine hundred names one at a time would take three hours;
the same endpoint with no ticker filter returns recent articles across the whole
market with the tickers already attached to each one, which covers the same
ground in a handful of calls.

What is stored: headline, publisher, timestamp, link. Never the article body —
that belongs to whoever wrote it, and a link is what sends them the reader.

This is the one part of the site that is somebody else's editorial judgement
rather than a number we computed. It is presented as such: a list of what was
published, with who published it, and no ranking, scoring or summarising of our
own on top.
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from collections.abc import Iterable

from data import settings

log = logging.getLogger(__name__)

# Enough pages to cover a day or two of market-wide coverage without spending
# the whole rate-limit budget on it.
MAX_PAGES = 8
PAGE_SIZE = 1000


def fetch(conn: sqlite3.Connection, since_days: int = 14,
          notice=None) -> int:
    """Pull recent market-wide articles into the cache. Returns rows written."""
    if settings.get("data.provider") == "synthetic":
        return _synthetic(conn, notice)

    from data.adapters.polygon import PolygonError, PolygonGroupedAdapter
    adapter = PolygonGroupedAdapter()
    cutoff = (dt.datetime.now(dt.timezone.utc)
              - dt.timedelta(days=since_days)).isoformat()

    written = 0
    params: dict[str, str] = {
        "order": "desc", "sort": "published_utc", "limit": str(PAGE_SIZE),
        "published_utc.gte": cutoff[:10],
    }
    path = "/v2/reference/news"
    for page in range(MAX_PAGES):
        try:
            payload = adapter._get(path, params if page == 0 else None)
        except PolygonError as exc:
            # News is not on every plan. A site without headlines is a site
            # without one section, not a broken nightly.
            if getattr(exc, "status", None) in (401, 403):
                if notice:
                    notice(f"News not available on this plan ({exc.status}). Skipped.")
                return 0
            if notice:
                notice(f"News fetch stopped: {exc}")
            return written
        except Exception as exc:                   # noqa: BLE001
            if notice:
                notice(f"News fetch stopped: {exc}")
            return written

        results = payload.get("results") or []
        if not results:
            break
        written += _store(conn, results)
        if notice:
            notice(f"news page {page + 1}: {len(results)} articles, {written:,} rows")
        nxt = payload.get("next_url")
        if not nxt:
            break
        path, params = nxt, None

    conn.commit()
    return written


def _store(conn: sqlite3.Connection, results: list[dict]) -> int:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    written = 0
    for row in results:
        article_id = str(row.get("id") or "").strip()
        title = (row.get("title") or "").strip()
        url = (row.get("article_url") or "").strip()
        published = (row.get("published_utc") or "").strip()
        publisher = ((row.get("publisher") or {}).get("name") or "").strip()
        tickers = [str(t).upper() for t in (row.get("tickers") or []) if t]
        if not (article_id and title and url and published and tickers):
            continue
        for symbol in dict.fromkeys(tickers):       # de-duplicated, order kept
            conn.execute(
                "INSERT OR REPLACE INTO news"
                "(article_id, symbol, published_at, title, publisher, url, fetched_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (article_id, symbol, published, title, publisher or "Unknown", url, now))
            written += 1
    return written


def prune(conn: sqlite3.Connection, keep_days: int = 45) -> int:
    """Old headlines are nobody's news. Keeps the table from growing forever."""
    cutoff = (dt.datetime.now(dt.timezone.utc)
              - dt.timedelta(days=keep_days)).isoformat()
    cur = conn.execute("DELETE FROM news WHERE published_at < ?", (cutoff,))
    conn.commit()
    return cur.rowcount


def by_symbol(conn: sqlite3.Connection, symbols: Iterable[str],
              limit: int = 6) -> dict[str, list[dict]]:
    """The most recent headlines for each symbol we hold any for."""
    wanted = {s.upper() for s in symbols}
    out: dict[str, list[dict]] = {}
    rows = conn.execute(
        "SELECT symbol, published_at, title, publisher, url FROM news"
        " ORDER BY published_at DESC")
    for row in rows:
        symbol = row["symbol"]
        if symbol not in wanted:
            continue
        held = out.setdefault(symbol, [])
        if len(held) >= limit:
            continue
        held.append({
            "published_at": row["published_at"],
            "title": row["title"],
            "publisher": row["publisher"],
            "url": row["url"],
        })
    return out


# What the site-wide list carries. Twelve was a home-page number that became
# the whole news page by accident when that page was built from the same call.
# The cache holds a couple of thousand articles over a fortnight, so a hundred
# is roughly the last day and a half — enough for the page to be worth opening
# and worth filtering, and still a small file.
MARKET_WIDE_LIMIT = 100


def market_wide(by_symbol_rows: dict[str, list[dict]],
                limit: int = MARKET_WIDE_LIMIT) -> list[dict]:
    """One recent-headlines list for the whole site, from the per-symbol map.

    An article usually carries several tickers, so the same headline appears
    under each of them. Deduplicating by URL and collecting the tickers back
    onto the article turns "six headlines each for nine hundred names" into a
    reading list, and keeps the same story from filling the page.

    No ranking or scoring of our own goes on top. The order is the order they
    were published, newest first, which is the only ordering that is a fact
    rather than an opinion.
    """
    articles: dict[str, dict] = {}
    for symbol, rows in by_symbol_rows.items():
        for row in rows:
            url = row.get("url")
            if not url:
                continue
            held = articles.get(url)
            if held is None:
                held = {**row, "tickers": []}
                articles[url] = held
            if symbol not in held["tickers"]:
                held["tickers"].append(symbol)

    out = sorted(articles.values(),
                 key=lambda a: a.get("published_at") or "", reverse=True)
    for article in out:
        article["tickers"] = sorted(article["tickers"])
    return out[:limit]


def _synthetic(conn: sqlite3.Connection, notice=None) -> int:
    """Headlines for the offline fixture.

    The fifth surface that could not be checked offline. Like the option spot,
    the volume spikes, the insider filings and the analyst estimates, this
    returned zero on the synthetic provider — so the news page, the home-page
    news card and every classification built on a headline rendered empty on
    every local build.

    The shapes matter, not just the volume: the legal and press-release
    headlines are here because the feed really does carry them and separating
    them from company analysis is the reason the classifier exists. A fixture
    with only clean analyst headlines could not test that at all.
    """
    import random                                  # noqa: PLC0415

    from data import store                         # noqa: PLC0415

    rng = random.Random(20260922)
    symbols = [r[0] for r in conn.execute(
        "SELECT symbol FROM universe WHERE passed = 1 ORDER BY symbol")]
    if not symbols:
        symbols = [r["symbol"] for r in store.ticker_rows(conn)][:400] \
            if hasattr(store, "ticker_rows") else []
    if not symbols:
        return 0

    publishers = ["Reuters", "Bloomberg", "Associated Press", "Barron's",
                  "MarketWatch", "Investor's Business Daily", "The Wall Street "
                  "Journal", "Seeking Alpha", "Benzinga", "GlobeNewswire",
                  "Business Wire", "PR Newswire", "Zacks"]
    analysis = [
        "{sym} clears a three-month base on heavy volume",
        "What {name} told investors about next quarter",
        "{name} lifts guidance as orders accelerate",
        "Analysts raise targets on {sym} after the print",
        "{name} margins widen for a third straight quarter",
        "{sym} names a new chief financial officer",
        "Why {name} is outrunning its industry this year",
        "{name} announces a $2bn buyback",
        "{sym} slides as a rival takes share",
        "{name} opens a second plant in Arizona",
    ]
    legal = [
        "DEADLINE ALERT: Investors in {sym} with losses are urged to contact "
        "counsel before the deadline",
        "CLASS ACTION filed on behalf of {name} shareholders",
        "{name} faces LAWSUIT over disclosures, firm says",
        "SHAREHOLDER ALERT: Investigation into {sym} announced",
        "INVESTOR DEADLINE approaching in the {name} securities litigation",
    ]
    releases = [
        "{name} to present at the Cowen technology conference",
        "{name} schedules third quarter results for next month",
        "{name} declares a quarterly dividend of $0.24 per share",
        "{name} completes acquisition of a logistics business",
    ]

    now = dt.datetime.now(dt.timezone.utc)
    written = 0
    for index in range(320):
        symbol = rng.choice(symbols)
        name = f"{symbol} Holdings"
        roll = rng.random()
        pool, publisher_pool = analysis, publishers[:9]
        if roll > 0.82:
            pool, publisher_pool = legal, publishers[9:12]
        elif roll > 0.66:
            pool, publisher_pool = releases, publishers[9:12]
        title = rng.choice(pool).format(sym=symbol, name=name)
        published = (now - dt.timedelta(
            hours=rng.randint(0, 14 * 24), minutes=rng.randint(0, 59)))
        tickers = [symbol]
        if rng.random() < 0.25:
            tickers.append(rng.choice(symbols))
        conn.execute(
            "INSERT OR REPLACE INTO news"
            "(article_id, symbol, published_at, title, publisher, url, fetched_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (f"syn-{index}", tickers[0],
             published.isoformat(timespec="seconds"), title,
             rng.choice(publisher_pool),
             f"https://example.invalid/{symbol.lower()}/{index}",
             now.isoformat(timespec="seconds")))
        written += 1
        for extra in tickers[1:]:
            conn.execute(
                "INSERT OR REPLACE INTO news"
                "(article_id, symbol, published_at, title, publisher, url, fetched_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (f"syn-{index}", extra,
                 published.isoformat(timespec="seconds"), title,
                 rng.choice(publisher_pool),
                 f"https://example.invalid/{symbol.lower()}/{index}",
                 now.isoformat(timespec="seconds")))
            written += 1
    conn.commit()
    if notice:
        notice(f"news: {written:,} synthetic rows (fixture).")
    return written


# ---------------------------------------------------------------- kinds
#
# Three kinds of headline arrive in this feed and they are not the same thing
# to a reader:
#
#   analysis   somebody wrote about the company
#   legal      a law firm advertising for plaintiffs. "DEADLINE ALERT",
#              "CLASS ACTION", "SHAREHOLDER ALERT" — these are paid wire
#              releases, they cluster after any sharp fall, and there are often
#              six of them for one event. They are not news about the business.
#   release    the company's own wire: results dates, dividends, conferences.
#              Factual, scheduled, and rarely a reason to do anything.
#
# Matched on the headline rather than the publisher, because the wires carry
# all three. A publisher-based rule would throw away real reporting that
# happened to cross PR Newswire.

LEGAL_MARKERS = (
    "deadline alert", "class action", "shareholder alert", "investor alert",
    "securities litigation", "investor deadline", "lawsuit", "investigation into",
    "law firm", "investors with losses", "class period",
)

RELEASE_MARKERS = (
    "to present at", "schedules", "declares a quarterly dividend",
    "announces the date", "conference call", "to report", "annual meeting",
    "completes acquisition", "appoints", "to participate in",
)

ANALYSIS = "analysis"
LEGAL = "legal"
RELEASE = "release"


def classify_headline(title: str) -> str:
    """Which of the three a headline is. Cheap, deterministic, checkable."""
    lowered = (title or "").lower()
    if any(marker in lowered for marker in LEGAL_MARKERS):
        return LEGAL
    if any(marker in lowered for marker in RELEASE_MARKERS):
        return RELEASE
    return ANALYSIS
