"""SQLite store with versioned migrations."""
from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3
from collections.abc import Iterable, Sequence

from data import settings
from data.types import Bar, TickerRef

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent / "migrations"


def connect(path: pathlib.Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or settings.db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply every migration not yet recorded. Returns the ones applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    applied: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (path.name, dt.datetime.utcnow().isoformat(timespec="seconds")),
        )
        applied.append(path.name)
    conn.commit()
    return applied


def open_db(path: pathlib.Path | None = None) -> sqlite3.Connection:
    conn = connect(path)
    migrate(conn)
    return conn


# ---------------------------------------------------------------- writes

def upsert_tickers(conn: sqlite3.Connection, refs: Iterable[TickerRef]) -> int:
    rows = [
        (r.symbol, r.name, r.type, r.exchange, r.industry,
         r.list_date.isoformat() if r.list_date else None, int(r.active))
        for r in refs
    ]
    conn.executemany(
        "INSERT INTO tickers(symbol,name,type,exchange,industry,list_date,active)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, type=excluded.type,"
        " exchange=excluded.exchange, industry=excluded.industry,"
        " list_date=COALESCE(excluded.list_date, tickers.list_date),"
        " active=excluded.active, updated_at=datetime('now')",
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_bars(conn: sqlite3.Connection, bars: Iterable[Bar]) -> int:
    rows = [
        (b.symbol, b.date.isoformat(), b.open, b.high, b.low, b.close, b.volume)
        for b in bars
    ]
    conn.executemany(
        "INSERT INTO bars(symbol,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(symbol,date) DO UPDATE SET open=excluded.open, high=excluded.high,"
        " low=excluded.low, close=excluded.close, volume=excluded.volume",
        rows,
    )
    conn.commit()
    return len(rows)


def get_shares(conn: sqlite3.Connection, max_age_days: int = 30) -> dict[str, float]:
    """Cached share counts still inside their freshness window."""
    rows = conn.execute(
        "SELECT symbol, shares_outstanding FROM fundamentals"
        " WHERE shares_outstanding IS NOT NULL"
        " AND fetched_at > datetime('now', ?)", (f"-{int(max_age_days)} days",))
    return {r["symbol"]: float(r["shares_outstanding"]) for r in rows}


def set_shares(conn: sqlite3.Connection, mapping: dict[str, float]) -> int:
    conn.executemany(
        "INSERT INTO fundamentals(symbol, shares_outstanding, fetched_at)"
        " VALUES (?,?,datetime('now'))"
        " ON CONFLICT(symbol) DO UPDATE SET shares_outstanding=excluded.shares_outstanding,"
        " fetched_at=datetime('now')",
        [(symbol, value) for symbol, value in mapping.items() if value])
    conn.commit()
    return len(mapping)


def set_industries(conn: sqlite3.Connection, mapping: dict[str, str]) -> int:
    conn.executemany(
        "UPDATE tickers SET industry=?, updated_at=datetime('now') WHERE symbol=?",
        [(industry, symbol) for symbol, industry in mapping.items() if industry])
    conn.commit()
    return len(mapping)


def set_kv(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO kv(key,value) VALUES (?,?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def get_kv(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def start_run(conn: sqlite3.Connection, stage: str) -> int:
    cur = conn.execute(
        "INSERT INTO runs(stage, started_at) VALUES (?, ?)",
        (stage, dt.datetime.utcnow().isoformat(timespec="seconds")),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, status: str, detail: str = "") -> None:
    conn.execute(
        "UPDATE runs SET finished_at=?, status=?, detail=? WHERE id=?",
        (dt.datetime.utcnow().isoformat(timespec="seconds"), status, detail, run_id),
    )
    conn.commit()


# ---------------------------------------------------------------- reads

def trading_dates(conn: sqlite3.Connection, limit: int | None = None) -> list[dt.date]:
    sql = "SELECT DISTINCT date FROM bars ORDER BY date"
    rows = conn.execute(sql).fetchall()
    dates = [dt.date.fromisoformat(r["date"]) for r in rows]
    return dates[-limit:] if limit else dates


def last_session(conn: sqlite3.Connection) -> dt.date | None:
    row = conn.execute("SELECT MAX(date) AS d FROM bars").fetchone()
    return dt.date.fromisoformat(row["d"]) if row and row["d"] else None


def load_series(conn: sqlite3.Connection, symbol: str, limit: int | None = None) -> list[Bar]:
    rows = conn.execute(
        "SELECT * FROM bars WHERE symbol=? ORDER BY date", (symbol,)
    ).fetchall()
    bars = [
        Bar(r["symbol"], dt.date.fromisoformat(r["date"]), r["open"], r["high"],
            r["low"], r["close"], r["volume"])
        for r in rows
    ]
    return bars[-limit:] if limit else bars


def load_many(conn: sqlite3.Connection, symbols: Sequence[str]) -> dict[str, list[Bar]]:
    if not symbols:
        return {}
    out: dict[str, list[Bar]] = {s: [] for s in symbols}
    marks = ",".join("?" * len(symbols))
    rows = conn.execute(
        f"SELECT * FROM bars WHERE symbol IN ({marks}) ORDER BY symbol, date", tuple(symbols)
    )
    for r in rows:
        out[r["symbol"]].append(
            Bar(r["symbol"], dt.date.fromisoformat(r["date"]), r["open"], r["high"],
                r["low"], r["close"], r["volume"])
        )
    return out


def all_symbols_with_bars(conn: sqlite3.Connection) -> list[str]:
    return [r["symbol"] for r in conn.execute("SELECT DISTINCT symbol FROM bars ORDER BY symbol")]


def get_ticker(conn: sqlite3.Connection, symbol: str) -> TickerRef | None:
    r = conn.execute("SELECT * FROM tickers WHERE symbol=?", (symbol,)).fetchone()
    if not r:
        return None
    return TickerRef(
        symbol=r["symbol"], name=r["name"], type=r["type"], exchange=r["exchange"],
        industry=r["industry"],
        list_date=dt.date.fromisoformat(r["list_date"]) if r["list_date"] else None,
        active=bool(r["active"]),
    )


def universe_symbols(conn: sqlite3.Connection) -> list[str]:
    return [r["symbol"] for r in
            conn.execute("SELECT symbol FROM universe WHERE passed=1 ORDER BY symbol")]


def universe_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM universe WHERE passed=1 ORDER BY symbol").fetchall()


def themes_for(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in conn.execute("SELECT symbol, theme_slug FROM theme_members ORDER BY symbol"):
        out.setdefault(r["symbol"], []).append(r["theme_slug"])
    return out
