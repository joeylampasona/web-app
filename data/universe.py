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
    conn.execute(f"DELETE FROM kv WHERE key LIKE '{CURSOR_PREFIX}%' OR key = '{BARS_PROVIDER_KEY}'")
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


# ---------------------------------------------------------------- backfill

def backfill(conn: sqlite3.Connection, adapter: DataAdapter | None = None,
             days: int | None = None, resume: bool = True,
             progress=None) -> int:
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

    written = 0
    day = start
    while day <= today:
        if day.weekday() < 5:
            bars: list[Bar] = adapter.get_grouped_daily(day)
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


def build(conn: sqlite3.Connection, adapter: DataAdapter | None = None) -> Funnel:
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

    shares = shares_outstanding([r["symbol"] for r, _, _ in priced])
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
            progress=None, reset: bool = False) -> Funnel:
    adapter = adapter or get_adapter()
    if reset:
        clear_bars(conn)
    check_provenance(conn, adapter.name)
    refresh_reference(conn, adapter)
    backfill(conn, adapter, progress=progress)
    return build(conn, adapter)
