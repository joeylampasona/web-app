"""Backfill, then the liquidity floor — in order, logging survivors at each stage."""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from dataclasses import dataclass, field

from data import classify, settings, store
from data.adapters import DataAdapter, get_adapter
from data.edgar import shares_outstanding
from data.types import Bar

log = logging.getLogger(__name__)

# The cursor is scoped per provider. One shared cursor meant that switching
# data.provider left the new provider resuming from the old one's position — and
# for a switch away from the fixture, whose cursor was stamped with today, that
# skipped the entire backfill in silence.
CURSOR_PREFIX = "backfill_cursor"
BARS_PROVIDER_KEY = "bars_provider"
HORIZON_PREFIX = "history_horizon"


def horizon_key(provider: str) -> str:
    return f"{HORIZON_PREFIX}:{provider}"


def cursor_key(provider: str) -> str:
    return f"{CURSOR_PREFIX}:{provider}"


class ProviderMismatch(RuntimeError):
    """The bars on disk were written by a different provider than the one configured."""


def check_provenance(conn: sqlite3.Connection, provider: str) -> None:
    """Refuse to mix one provider's prices with another's tickers.

    Bars with no recorded provenance are treated as foreign too: they predate
    this check, so they could have come from anywhere.
    """
    bars = conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    if not bars:
        return
    written_by = store.get_kv(conn, BARS_PROVIDER_KEY)
    if written_by == provider:
        return
    whose = f"the '{written_by}' provider" if written_by else "an earlier run, before we recorded which"
    raise ProviderMismatch(
        f"This database already holds {bars:,} bars written by {whose}, but "
        f"data.provider is now '{provider}'. Mixing them builds the universe from "
        f"one provider's ticker list and another's prices, which looks plausible "
        f"and is wrong. Clear them and start this provider's backfill cleanly:\n\n"
        f"    python -m cli universe --refresh --reset")


def clear_bars(conn: sqlite3.Connection) -> int:
    """Drop every bar and every cursor. Used when switching provider."""
    count = conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    conn.execute("DELETE FROM bars")
    conn.execute("DELETE FROM universe")
    conn.execute(
        f"DELETE FROM kv WHERE key LIKE '{CURSOR_PREFIX}%' "
        f"OR key LIKE '{HORIZON_PREFIX}%' OR key = '{BARS_PROVIDER_KEY}'")
    conn.commit()
    return int(count)


@dataclass
class Stage:
    name: str
    survivors: int
    dropped: int


@dataclass
class Funnel:
    stages: list[Stage] = field(default_factory=list)
    final: int = 0
    as_of: dt.date | None = None

    def add(self, name: str, survivors: int, previous: int) -> None:
        self.stages.append(Stage(name, survivors, max(0, previous - survivors)))

    def render(self) -> str:
        width = max(len(s.name) for s in self.stages) if self.stages else 10
        lines = [f"Universe funnel — as of {self.as_of or 'n/a'}", ""]
        for s in self.stages:
            lines.append(f"  {s.name.ljust(width)}  {s.survivors:>6,}   (-{s.dropped:,})")
        lines.append("")
        lines.append(f"  {'FINAL'.ljust(width)}  {self.final:>6,}")
        return "\n".join(lines)


# ---------------------------------------------------------------- horizon

def _serves(adapter: DataAdapter, day: dt.date) -> bool:
    """Will the plan return this session at all? A 403 means it will not."""
    from data.adapters.polygon import PolygonError
    try:
        adapter.get_grouped_daily(day)
        return True
    except PolygonError as exc:
        if getattr(exc, "status", None) == 403:
            return False
        raise


def _weekday(day: dt.date) -> dt.date:
    """Snap forward to a weekday. For the old end of a range."""
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day


def _latest_served(adapter: DataAdapter, latest: dt.date, attempts: int = 8) -> dt.date | None:
    """The most recent session the plan will actually serve, walking backwards.

    Three things make "today" the wrong probe: it can be a weekend, it can be a
    holiday, and a delayed tier may not have published the last session yet.
    Snapping forward to the next weekday — which is what this used to do — can
    land on a date that has not happened, and the provider refuses it.
    """
    day = latest
    for _ in range(attempts):
        while day.weekday() >= 5:
            day -= dt.timedelta(days=1)
        if _serves(adapter, day):
            return day
        day -= dt.timedelta(days=1)
    return None


def find_history_horizon(adapter: DataAdapter, earliest: dt.date, latest: dt.date,
                         notice=None) -> dt.date:
    """The oldest session this plan will serve.

    Free tiers cap how far back grouped aggregates go, and the cap is a 403 on
    the individual date rather than anything you can read off the account.
    Walking backwards a day at a time would burn hundreds of calls at five a
    minute, so bisect: about eleven calls covers four years.
    """
    lo = _weekday(earliest)
    hi = _latest_served(adapter, latest)
    if hi is None:
        raise ProviderMismatch(
            f"This plan served grouped daily aggregates for none of the eight "
            f"sessions before {latest}. That endpoint is the premise of this "
            f"build — check the key and the plan before going further.")
    if _serves(adapter, lo):
        return lo
    if notice:
        notice(f"{lo} is outside this plan's history window — finding the oldest "
               f"session it will serve (about a dozen calls, three minutes).")
    while (hi - lo).days > 1:
        mid = _weekday(lo + dt.timedelta(days=(hi - lo).days // 2))
        if mid >= hi:
            break
        if _serves(adapter, mid):
            hi = mid
        else:
            lo = mid
    return hi


# ---------------------------------------------------------------- backfill

def backfill(conn: sqlite3.Connection, adapter: DataAdapter | None = None,
             days: int | None = None, resume: bool = True,
             progress=None, notice=None) -> int:
    """One grouped-daily call per past session, resumable at the cursor."""
    adapter = adapter or get_adapter()
    days = days or int(settings.get("data.backfill_days", 520))

    check_provenance(conn, adapter.name)
    key = cursor_key(adapter.name)

    if adapter.name == "synthetic":
        bars = adapter.all_bars()               # fixture: no per-session calls
        written = store.upsert_bars(conn, bars)
        refs = adapter.get_universe()
        store.upsert_tickers(conn, refs)
        # Its own last session, never today: stamping today would make a later
        # resume think there is nothing left to fetch.
        store.set_kv(conn, key, max(b.date for b in bars).isoformat() if bars else "")
        store.set_kv(conn, BARS_PROVIDER_KEY, adapter.name)
        return written

    today = dt.date.today()
    start = today - dt.timedelta(days=int(days * 1.45))   # weekends and holidays
    cursor = store.get_kv(conn, key)
    if resume and cursor:
        start = max(start, dt.date.fromisoformat(cursor) + dt.timedelta(days=1))

    # Respect the plan's history window rather than throwing 403s at it.
    known = store.get_kv(conn, horizon_key(adapter.name))
    horizon = dt.date.fromisoformat(known) if known else None
    if horizon is None:
        horizon = find_history_horizon(adapter, start, today, notice)
        store.set_kv(conn, horizon_key(adapter.name), horizon.isoformat())
    if horizon > start:
        if notice:
            notice(f"This plan serves history back to {horizon}. Backfilling from "
                   f"there — about {(today - horizon).days * 5 // 7:,} sessions.")
        start = horizon

    from data.adapters.polygon import PolygonError

    written = 0
    day = start
    while day <= today:
        if day.weekday() < 5:
            try:
                bars: list[Bar] = adapter.get_grouped_daily(day)
            except PolygonError as exc:
                # The most recent session may not be published on a delayed tier.
                # That is a "come back tomorrow", not a failure of the run.
                if getattr(exc, "status", None) == 403:
                    if notice:
                        notice(f"{day} is not available on this plan yet — stopping "
                               f"here. Re-run tomorrow to pick it up.")
                    break
                raise
            if bars:
                written += store.upsert_bars(conn, bars)
            store.set_kv(conn, key, day.isoformat())
            if progress:
                progress(day, len(bars))
        day += dt.timedelta(days=1)
    store.set_kv(conn, BARS_PROVIDER_KEY, adapter.name)
    return written


def refresh_reference(conn: sqlite3.Connection, adapter: DataAdapter | None = None) -> int:
    adapter = adapter or get_adapter()
    refs = adapter.get_universe()
    return store.upsert_tickers(conn, refs)


# ---------------------------------------------------------------- the floor

def _is_common_stock(row: sqlite3.Row, allowed: list[str], fragments: list[str]) -> bool:
    if (row["type"] or "").upper() not in allowed:
        return False
    name = (row["name"] or "").upper()
    return not any(frag.upper() in name for frag in fragments)


def build(conn: sqlite3.Connection, adapter: DataAdapter | None = None,
          notice=None) -> Funnel:
    cfg = settings.get("universe", {}) or {}
    allowed = [t.upper() for t in cfg.get("allowed_types", ["CS"])]
    fragments = cfg.get("exclude_name_fragments", []) or []
    min_price = float(cfg.get("min_price", 5.0))
    min_cap = float(cfg.get("min_market_cap", 3e8))
    min_adv = float(cfg.get("min_avg_dollar_volume", 5e6))
    lookback = int(cfg.get("dollar_volume_lookback", 20))

    as_of = store.last_session(conn)
    funnel = Funnel(as_of=as_of)
    if as_of is None:
        funnel.add("all reference tickers", 0, 0)
        return funnel

    refs = conn.execute("SELECT * FROM tickers").fetchall()
    total = len(refs)
    funnel.add("all reference tickers", total, total)

    commons = [r for r in refs if _is_common_stock(r, allowed, fragments)]
    funnel.add("US common stocks only", len(commons), total)

    symbols = [r["symbol"] for r in commons]
    if notice:
        notice(f"Loading bars for {len(symbols):,} names out of the database — "
               f"a minute or two, no output while it works.")
    series = store.load_many(conn, symbols)

    # Having a bar on the latest session is its own stage. Folded into the price
    # filter it hides the difference between "this stock is cheap" and "we have
    # no prices for this stock at all", which is the failure that actually bites.
    quoted: list[tuple[sqlite3.Row, list]] = []
    for r in commons:
        bars = series.get(r["symbol"]) or []
        if bars and bars[-1].date == as_of:
            quoted.append((r, bars))
    funnel.add(f"has a bar on {as_of}", len(quoted), len(commons))

    priced: list[tuple[sqlite3.Row, float, float]] = []
    for r, bars in quoted:
        close = bars[-1].close
        if close <= min_price:
            continue
        window = bars[-lookback:]
        adv = sum(b.close * b.volume for b in window) / max(1, len(window))
        priced.append((r, close, adv))
    funnel.add(f"price > ${min_price:,.0f}", len(priced), len(quoted))

    wanted = [r["symbol"] for r, _, _ in priced]
    if notice:
        notice(f"Asking SEC EDGAR for shares outstanding on {len(wanted):,} "
               f"companies. Rate-limited, so expect 15-30 minutes.")

    def edgar_progress(done: int, total: int, found: int) -> None:
        if notice:
            notice(f"  EDGAR {done:,}/{total:,} — {found:,} share counts so far")

    shares = shares_outstanding(wanted, progress=edgar_progress)
    capped: list[tuple[sqlite3.Row, float, float, float]] = []
    for r, close, adv in priced:
        sh = shares.get(r["symbol"])
        if not sh:
            continue
        cap = sh * close
        if cap <= min_cap:
            continue
        capped.append((r, close, adv, cap))
    funnel.add(f"market cap > ${min_cap/1e6:,.0f}M", len(capped), len(priced))

    liquid = [row for row in capped if row[2] > min_adv]
    funnel.add(f"{lookback}-day avg $ volume > ${min_adv/1e6:,.0f}M", len(liquid), len(capped))
    funnel.final = len(liquid)

    conn.execute("DELETE FROM universe")
    conn.executemany(
        "INSERT INTO universe(symbol, as_of, price, market_cap, adv20, industry, passed)"
        " VALUES (?,?,?,?,?,?,1)",
        [(r["symbol"], as_of.isoformat(), close, cap, adv, r["industry"] or "Unclassified")
         for r, close, adv, cap in liquid],
    )
    conn.commit()

    classify.write_theme_members(
        conn, [(r["symbol"], r["industry"] or "", cap) for r, _, _, cap in liquid])
    return funnel


def refresh(conn: sqlite3.Connection, adapter: DataAdapter | None = None,
            progress=None, reset: bool = False, notice=None) -> Funnel:
    adapter = adapter or get_adapter()
    if reset:
        clear_bars(conn)
    check_provenance(conn, adapter.name)
    refresh_reference(conn, adapter)
    backfill(conn, adapter, progress=progress, notice=notice)
    return build(conn, adapter, notice=notice)
