"""Dated events for the tickers currently on a screen.

Four types are ingested: earnings, dividend ex-dates, splits and index changes.
Index changes have no free automatic source that we trust, so that type exists
in the schema and stays empty rather than being filled by hand.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from data import settings
from data.adapters import DataAdapter, get_adapter
from data.market import Market

log = logging.getLogger(__name__)

EARNINGS = "earnings"
DIVIDEND = "dividend_ex_date"
SPLIT = "split"
INDEX = "index_change"

TYPE_LABELS = {
    EARNINGS: "Earnings",
    DIVIDEND: "Ex-dividend",
    SPLIT: "Split",
    INDEX: "Index change",
}

# supplier is in the vocabulary but never emitted: we have no free, automatic
# supply-chain source, and asserting a supplier relationship we cannot evidence
# would be inventing data.
READTHROUGH_TAGS = ("supplier", "competitor", "industry")


@dataclass
class Event:
    ticker: str
    type: str
    date: dt.date
    confirmed: str = "tentative"        # confirmed | tentative | window
    title: str = ""
    details: str = ""
    readthrough: dict | None = None     # {from, tag, label} when it is a peer's event

    def days_until(self, as_of: dt.date) -> int:
        return (self.date - as_of).days

    def to_json(self, as_of: dt.date) -> dict:
        out = asdict(self)
        out["date"] = self.date.isoformat()
        out["days_until"] = self.days_until(as_of)
        out["type_label"] = TYPE_LABELS.get(self.type, self.type)
        return out


@dataclass
class Calendar:
    as_of: dt.date
    by_ticker: dict[str, list[Event]] = field(default_factory=dict)

    def add(self, event: Event) -> None:
        self.by_ticker.setdefault(event.ticker, []).append(event)

    def sorted_for(self, ticker: str) -> list[Event]:
        return sorted(self.by_ticker.get(ticker, []), key=lambda e: e.date)

    def next_earnings(self, ticker: str) -> Event | None:
        for event in self.sorted_for(ticker):
            if event.type == EARNINGS and event.readthrough is None \
                    and event.date >= self.as_of:
                return event
        return None

    def next_owned(self, ticker: str) -> Event | None:
        """The next event the ticker owns itself. Readthroughs do not qualify."""
        for event in self.sorted_for(ticker):
            if event.readthrough is None and event.date >= self.as_of:
                return event
        return None


# ---------------------------------------------------------------- ingestion

def _synthetic_extras(adapter, symbols: Sequence[str], as_of: dt.date) -> list[Event]:
    import random
    events: list[Event] = []
    for symbol in symbols:
        rng = random.Random(hash((symbol, "extras")) & 0xFFFF)
        if rng.random() < 0.35:
            date = as_of + dt.timedelta(days=rng.randint(3, 70))
            events.append(Event(symbol, DIVIDEND, date, "confirmed",
                                "Ex-dividend date"))
        if rng.random() < 0.06:
            date = as_of + dt.timedelta(days=rng.randint(10, 80))
            events.append(Event(symbol, SPLIT, date, "tentative", "Stock split"))
    return events


def _polygon_extras(adapter: DataAdapter, symbols: Sequence[str],
                    as_of: dt.date) -> list[Event]:
    """Dividends and splits in two calls, not two per ticker."""
    wanted = set(symbols)
    events: list[Event] = []
    horizon = as_of + dt.timedelta(days=int(settings.get("catalysts.lookahead_days", 90)))
    try:
        payload = adapter._get("/v3/reference/dividends", {                # noqa: SLF001
            "ex_dividend_date.gte": as_of.isoformat(),
            "ex_dividend_date.lte": horizon.isoformat(), "limit": 1000})
        for row in payload.get("results", []):
            if row.get("ticker") in wanted and row.get("ex_dividend_date"):
                events.append(Event(row["ticker"], DIVIDEND,
                                    dt.date.fromisoformat(row["ex_dividend_date"]),
                                    "confirmed", "Ex-dividend date",
                                    f"{row.get('cash_amount', '')} per share"))
    except Exception as exc:                      # noqa: BLE001
        log.warning("dividend ingestion skipped: %s", exc)
    try:
        payload = adapter._get("/v3/reference/splits", {                   # noqa: SLF001
            "execution_date.gte": as_of.isoformat(),
            "execution_date.lte": horizon.isoformat(), "limit": 1000})
        for row in payload.get("results", []):
            if row.get("ticker") in wanted and row.get("execution_date"):
                ratio = f"{row.get('split_from', '')}-for-{row.get('split_to', '')}"
                events.append(Event(row["ticker"], SPLIT,
                                    dt.date.fromisoformat(row["execution_date"]),
                                    "confirmed", "Stock split", ratio))
    except Exception as exc:                      # noqa: BLE001
        log.warning("split ingestion skipped: %s", exc)
    return events


def index_changes(symbols: Sequence[str], as_of: dt.date) -> list[Event]:
    """Index additions and deletions.

    There is no free, automatic feed for these that we are willing to depend on.
    The type exists so the timeline can carry it the day one appears; until then
    this returns nothing rather than inviting a hand-maintained list.
    """
    return []


# What the desk's `hour` field means, said plainly. An empty hour is unknown,
# and unknown is not "after the close" — that guess is what this replaces.
_HOUR_NOTE = {
    "bmo": "Reports before the open.",
    "amc": "Reports after the close.",
    "": "The company has not said whether it reports before the open or after "
        "the close, so treat both ends of that session as exposed.",
}


def build(market: Market, symbols: Sequence[str],
          adapter: DataAdapter | None = None,
          desk_earnings: dict[str, tuple[dt.date, str]] | None = None,
          conn=None, notice=None) -> Calendar:
    adapter = adapter or get_adapter()
    as_of = market.as_of
    calendar = Calendar(as_of=as_of)
    horizon = as_of + dt.timedelta(days=int(settings.get("catalysts.lookahead_days", 90)))
    symbols = sorted(set(symbols))

    # Earnings dates come from a per-ticker scrape that Yahoo rate-limits well
    # before two thousand names are through it. With a connection they are
    # cached: only the names without a recent date are asked for, and whatever
    # arrives is kept. A throttled night then costs the names it missed rather
    # than every name, which is what used to happen — 62% of pages published an
    # empty roadmap for companies that certainly report inside the window.
    from catalysts import yf as yfmod
    ask_for = list(symbols)
    if conn is not None:
        try:
            ask_for = yfmod.stale_symbols(conn, symbols)
            if notice:
                notice(f"earnings: {len(symbols) - len(ask_for):,} names already "
                       f"have a recent date, asking about {len(ask_for):,}.")
        except Exception as exc:                  # noqa: BLE001
            log.warning("earnings cache unreadable, asking about everything: %s", exc)

    try:
        fetched = adapter.get_earnings_dates(ask_for) if ask_for else {}
    except NotImplementedError:
        fetched = {}
    except Exception as exc:                      # noqa: BLE001
        log.warning("earnings ingestion failed: %s", exc)
        fetched = {}

    earnings = dict(fetched)
    if conn is not None:
        try:
            yfmod.store_dates(conn, fetched)
            # Everything known, not just tonight's haul.
            for symbol, events in yfmod.load_dates(conn, symbols, as_of).items():
                earnings.setdefault(symbol, events)
            if notice:
                got = sum(1 for v in earnings.values() if v)
                notice(f"earnings: {len(fetched):,} names fetched tonight, "
                       f"{got:,} of {len(symbols):,} have a date in total.")
        except Exception as exc:                  # noqa: BLE001
            log.warning("earnings cache unusable: %s", exc)

    # The Market Desk is authoritative where it has a date: it reads them from a
    # dedicated source and carries the session half, where our own fallback is
    # scraped and has to assume. It covers only the small share of the market
    # reporting in any three-week window, though, so this is precedence and not
    # replacement — and a symbol absent from it is not a symbol with no earnings
    # coming, which is what its own schema says too.
    desk = desk_earnings or {}
    for symbol, (date, hour) in desk.items():
        if symbol in set(symbols) and as_of <= date <= horizon:
            # "confirmed", not True: this field is a three-way string and a bool
            # would render as a status nothing on the site knows how to read.
            # The desk takes its dates from a dedicated source, so confirmed is
            # the honest value where it has one.
            calendar.add(Event(symbol, EARNINGS, date, "confirmed",
                               "Quarterly earnings",
                               _HOUR_NOTE.get(hour, _HOUR_NOTE[""])))

    for symbol, rows in earnings.items():
        if symbol in desk:
            continue                # already dated by a better source
        for row in rows:
            if not (as_of <= row.date <= horizon):
                continue
            calendar.add(Event(symbol, EARNINGS, row.date, row.confirmed,
                               "Quarterly earnings",
                               "Reported after the close unless the company says otherwise."))

    extras = (_synthetic_extras(adapter, symbols, as_of) if adapter.name == "synthetic"
              else _polygon_extras(adapter, symbols, as_of))
    for event in extras + list(index_changes(symbols, as_of)):
        if as_of <= event.date <= horizon:
            calendar.add(event)

    _add_readthrough(market, calendar, symbols)
    return calendar


def _add_readthrough(market: Market, calendar: Calendar, symbols: Sequence[str]) -> None:
    """A peer's dated event, when the peer is the biggest name in a shared theme.

    Kept deliberately narrow. One large name's earnings bearing on its theme is
    defensible; every name in a theme reading through to every other is noise.
    """
    if not settings.get("catalysts.readthrough.enabled", True):
        return
    universe = set(symbols)
    by_theme: dict[str, list[str]] = {}
    for symbol in universe:
        for slug in market.themes.get(symbol, []):
            by_theme.setdefault(slug, []).append(symbol)

    limit = int(settings.get("catalysts.readthrough.largest_per_theme", 1))
    emitted: set[tuple[str, str, str, dt.date]] = set()
    for slug, members in by_theme.items():
        if len(members) < 2:
            continue
        ordered = sorted(members, key=lambda s: -market.caps.get(s, 0.0))
        for source in ordered[:limit]:
            for event in list(calendar.by_ticker.get(source, [])):
                if event.readthrough is not None or event.type != EARNINGS:
                    continue
                for peer in members:
                    if peer == source:
                        continue
                    key = (peer, source, event.type, event.date)
                    if key in emitted:      # two shared themes is still one event
                        continue
                    emitted.add(key)
                    tag = ("competitor"
                           if market.industries.get(peer) == market.industries.get(source)
                           else "industry")
                    calendar.add(Event(
                        ticker=peer, type=event.type, date=event.date,
                        confirmed=event.confirmed,
                        title=f"{source} reports",
                        details=f"{source} is the largest name in this theme. Its "
                                f"results are read across to its peers.",
                        readthrough={"from": source, "tag": tag, "theme": slug}))


def attach(calendar: Calendar, setups) -> None:
    """Stamp every setup with its next earnings date, the 7-day flag and a roadmap."""
    badge_days = int(settings.get("catalysts.earnings_badge_days", 7))
    for setup in setups:
        events = calendar.sorted_for(setup.symbol)
        nxt = calendar.next_earnings(setup.symbol)
        days = nxt.days_until(calendar.as_of) if nxt else None
        setup.catalysts = {
            "next_earnings_date": nxt.date.isoformat() if nxt else None,
            "days_until_earnings": days,
            "earnings_within_7d": bool(days is not None and 0 <= days <= badge_days),
            "catalyst_roadmap": [e.to_json(calendar.as_of) for e in events],
        }
