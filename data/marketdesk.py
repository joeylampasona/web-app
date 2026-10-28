"""Signals ingested from the Market Desk repository.

That project sweeps the whole US market overnight — filings, insider clusters,
tape anomalies, sentiment, earnings dates — and writes `signals/YYYY-MM-DD.json`
against a documented, versioned contract. It was built to be read by another
repository; this is the other repository.

Three things in that contract are load-bearing and are honoured here rather
than assumed:

* **The major version is pinned.** Fields may be added within a major version
  and never removed or renamed. A major bump means the shape changed, so this
  refuses to parse rather than guessing.
* **`stage_status` separates a quiet market from a broken scanner.** An empty
  TAPE set means nothing if the tape scanner failed, so the status is stored
  and shown, not dropped.
* **An unknown `reason` is informational, not an error.** New ones may appear
  at any time. Anything unrecognised is kept and displayed plainly rather than
  discarded or crashed on.

Its earnings dates do not replace ours. The desk covers only the small share of
the market reporting in any three-week window — a couple of per cent on a given
night — so it is authoritative where it has a date and silent where it does
not, which is precedence rather than replacement. Its own schema says plainly
that a ticker's absence is not evidence it has no earnings coming.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
from typing import Any

import requests

from data import settings

log = logging.getLogger(__name__)

SCHEMA_MAJOR = 1
# The desk writes one file a night; a run may be a day or two behind ours after
# a holiday, so walk back rather than giving up on the first miss.
LOOKBACK_DAYS = 6


class DeskUnavailable(RuntimeError):
    """The desk could not be read. Never fatal — the site has its own data."""


class DeskSchemaChanged(RuntimeError):
    """A major version bump. Refuse to parse rather than guess at the shape."""


def _config() -> tuple[str, str]:
    cfg = settings.get("marketdesk", {}) or {}
    repo = cfg.get("repo", "")
    token = settings.env(cfg.get("token_env", "MARKET_DESK_TOKEN"))
    return repo, token


def enabled() -> bool:
    repo, token = _config()
    return bool(repo and token)


def _fetch_file(repo: str, token: str, path: str) -> dict[str, Any] | None:
    """One signals file, or None when that date does not exist."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    resp = requests.get(url, timeout=30, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    if resp.status_code == 404:
        return None
    if resp.status_code in (401, 403):
        raise DeskUnavailable(
            f"GitHub refused the Market Desk read (HTTP {resp.status_code}). The "
            f"token needs read access to {repo} and it may have expired.")
    if not resp.ok:
        raise DeskUnavailable(f"HTTP {resp.status_code} reading {path} from {repo}.")
    try:
        return json.loads(resp.text)
    except json.JSONDecodeError as exc:
        raise DeskUnavailable(f"{path} is not valid JSON: {exc}") from exc


def ingest(conn: sqlite3.Connection, as_of: dt.date, notice=None) -> dict:
    """Read the most recent desk run at or before `as_of` into the database."""
    repo, token = _config()
    if not (repo and token):
        return {"status": "not configured"}

    payload = None
    used: dt.date | None = None
    for back in range(LOOKBACK_DAYS):
        day = as_of - dt.timedelta(days=back)
        payload = _fetch_file(repo, token, f"signals/{day.isoformat()}.json")
        if payload:
            used = day
            break
    if not payload or used is None:
        raise DeskUnavailable(
            f"No desk run found in the {LOOKBACK_DAYS} days to {as_of}. The desk "
            "may not have run, or may be behind.")

    version = str(payload.get("schema_version") or "0")
    major = version.split(".")[0]
    if major != str(SCHEMA_MAJOR):
        raise DeskSchemaChanged(
            f"Market Desk is on schema {version}; this reads major "
            f"{SCHEMA_MAJOR}. Fields are never removed within a major version, "
            "so a bump means the shape changed and parsing it blind would put "
            "wrong numbers on the site.")

    stage_status = payload.get("stage_status") or {}
    signals = payload.get("signals") or []
    earnings = payload.get("earnings") or []
    stamp = used.isoformat()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    conn.execute("DELETE FROM desk_signals WHERE as_of = ?", (stamp,))
    kept = 0
    for row in signals:
        ticker = str(row.get("ticker") or "").upper()
        source = str(row.get("source") or "").upper()
        reason = str(row.get("reason") or "").upper()
        if not (ticker and source and reason):
            continue
        conn.execute(
            "INSERT OR REPLACE INTO desk_signals"
            "(as_of, symbol, source, reason, detail, magnitude, url)"
            " VALUES (?,?,?,?,?,?,?)",
            (stamp, ticker, source, reason, str(row.get("detail") or ""),
             row.get("magnitude"), str(row.get("url") or "")))
        kept += 1

    dates = 0
    for row in earnings:
        ticker = str(row.get("ticker") or "").upper()
        report = str(row.get("report_date") or "")
        if not (ticker and report):
            continue
        conn.execute(
            "INSERT OR REPLACE INTO desk_earnings(symbol, report_date, hour, as_of)"
            " VALUES (?,?,?,?)",
            (ticker, report, str(row.get("hour") or ""), stamp))
        dates += 1

    # The desk's scorecard and its positioning table, kept whole. Both are
    # optional within the major version -- edge since 1.1, positioning since
    # 1.5 -- so their absence is stored as empty, not treated as a fault.
    edge = payload.get("edge") if isinstance(payload.get("edge"), list) else []
    positioning = payload.get("positioning")
    if not (isinstance(positioning, dict) and positioning.get("markets")):
        positioning = None
    # 1.6 and 1.7 blocks, each optional: absent on an older run, null on a
    # night the desk had nothing, and stored as null either way.
    context = payload.get("market_context")
    context = context if isinstance(context, dict) else None
    earn_iv = payload.get("earnings_iv")
    earn_iv = earn_iv if isinstance(earn_iv, dict) else None
    holders = payload.get("holders")
    holders = holders if isinstance(holders, dict) and holders.get("by_ticker") else None
    conn.execute(
        "INSERT OR REPLACE INTO desk_runs"
        "(as_of, generated_at, schema_version, universe_size, stage_status,"
        " fetched_at, edge, positioning, market_context, earnings_iv, holders)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (stamp, str(payload.get("generated_at_utc") or ""), version,
         payload.get("universe_size"), json.dumps(stage_status), now,
         json.dumps(edge), json.dumps(positioning), json.dumps(context),
         json.dumps(earn_iv), json.dumps(holders)))
    if holders:
        # Half a megabyte a night, in a database the nightly caches whole.
        # Only the newest copy is ever read.
        conn.execute("UPDATE desk_runs SET holders = 'null' WHERE as_of < ?", (stamp,))
    conn.commit()

    if notice:
        broken = [k for k, v in stage_status.items() if v != "ok"]
        notice(f"Market Desk {stamp}: {kept:,} signals, {dates:,} earnings dates"
               + (f" — scanners not ok: {', '.join(broken)}" if broken else ""))
    return {"status": "ok", "as_of": stamp, "signals": kept,
            "earnings": dates, "stage_status": stage_status}


def latest_run(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM desk_runs ORDER BY as_of DESC LIMIT 1").fetchone()
    if not row:
        return None
    return {"as_of": row["as_of"], "generated_at": row["generated_at"],
            "universe_size": row["universe_size"],
            "stage_status": json.loads(row["stage_status"] or "{}")}


def track_records(conn: sqlite3.Connection) -> dict[tuple[str, str], dict]:
    """The desk's scorecard from its latest run, keyed by (source, reason).

    Only the fields a reader can act on: the verdict, how many signals it rests
    on, the excess three-day return over random unflagged names, and which way
    the type claims the stock should go. The
    t-statistic and the win rates stay in the desk, where its own dashboard
    explains them.
    """
    row = conn.execute(
        "SELECT edge FROM desk_runs ORDER BY as_of DESC LIMIT 1").fetchone()
    if not row:
        return {}
    try:
        table = json.loads(row["edge"] or "[]")
    except (TypeError, ValueError):
        return {}
    out: dict[tuple[str, str], dict] = {}
    for r in table if isinstance(table, list) else []:
        source, reason = str(r.get("source") or ""), str(r.get("reason") or "")
        if not (source and reason):
            continue
        out[(source.upper(), reason.upper())] = {
            "read": str(r.get("read") or ""),
            "n": r.get("n"),
            "excess3": r.get("excess3"),
            # +1 the type claims the stock goes up, -1 down, 0 no claim. The
            # desk's "edge" on a type with no claim means only a reliable
            # effect, in either direction -- gaps have lagged random names,
            # and are scored "edge" for it. Without this a page would read
            # that as a recommendation.
            "thesis": r.get("thesis") or 0,
            # The sign of a measured effect, for types that claim none.
            "direction": r.get("direction") or 0,
            # Against the stock's own sector over the same sessions, so a
            # type that only rode its sector's good week reads as that.
            "excess_sector3": r.get("excess_sector3"),
            "n_sector": r.get("n_sector"),
            # Separate nights the verdict rests on. Signals on one night
            # share a market; the desk's verdict is computed per night.
            "nights": r.get("nights"),
        }
    return out


def positioning(conn: sqlite3.Connection) -> dict | None:
    """The newest CFTC positioning table any stored run carried.

    The newest run with one, not just the newest run: the table is weekly, and
    a run from before the desk's 1.5 export or a night the desk dropped it
    should not blank a panel whose data is still the current week's.
    """
    for row in conn.execute(
            "SELECT positioning FROM desk_runs ORDER BY as_of DESC LIMIT 10"):
        try:
            table = json.loads(row["positioning"] or "null")
        except (TypeError, ValueError):
            continue
        if isinstance(table, dict) and table.get("markets"):
            return table
    return None


def _newest_block(conn: sqlite3.Connection, column: str, runs: int):
    """The newest non-null JSON block in `column` over the last `runs` runs."""
    for row in conn.execute(
            f"SELECT {column} FROM desk_runs ORDER BY as_of DESC LIMIT ?", (runs,)):
        try:
            value = json.loads(row[column] or "null")
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict) and value:
            return value
    return None


def market_context(conn: sqlite3.Connection) -> dict | None:
    """CBOE put/call and the desk's regime label, from the newest run only.

    The newest run, not the newest with a reading: the desk already nulls a
    reading past its own clock, and reaching back to an older run would undo
    exactly that and file last week's ratio as tonight's.
    """
    row = conn.execute(
        "SELECT market_context FROM desk_runs ORDER BY as_of DESC LIMIT 1").fetchone()
    if not row:
        return None
    try:
        value = json.loads(row["market_context"] or "null")
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    if not (value.get("put_call") or value.get("regime")):
        return None
    return {"put_call": value.get("put_call"), "regime": value.get("regime")}


def earnings_iv(conn: sqlite3.Connection) -> dict | None:
    """The priced-against-realised earnings read from the last few runs."""
    return _newest_block(conn, "earnings_iv", 3)


def holders(conn: sqlite3.Connection) -> dict | None:
    """The tracked funds' 13F holders per ticker. Quarterly, so a run or two
    without the block does not empty it."""
    return _newest_block(conn, "holders", 10)


def earnings_dates(conn: sqlite3.Connection) -> dict[str, tuple[dt.date, str]]:
    """Symbol to (date, hour). Authoritative where present, absent otherwise."""
    out: dict[str, tuple[dt.date, str]] = {}
    for row in conn.execute("SELECT symbol, report_date, hour FROM desk_earnings"):
        try:
            out[row["symbol"]] = (dt.date.fromisoformat(row["report_date"]),
                                  row["hour"] or "")
        except (TypeError, ValueError):
            continue
    return out


def by_symbol(conn: sqlite3.Connection, symbols, limit: int = 8) -> dict[str, list[dict]]:
    """The most recent desk signals per symbol, newest run first.

    Each carries `track`: the desk's own verdict on that signal type, or null
    when the desk has not scored it. A signal shown without it reads as a
    recommendation, and the desk's scorecard says several types -- large
    insider buys among them -- have moved against their own claim.
    """
    wanted = {s.upper() for s in symbols}
    tracks = track_records(conn)
    out: dict[str, list[dict]] = {}
    rows = conn.execute(
        "SELECT as_of, symbol, source, reason, detail, magnitude, url"
        " FROM desk_signals ORDER BY as_of DESC, source, reason")
    for row in rows:
        symbol = row["symbol"]
        if symbol not in wanted:
            continue
        held = out.setdefault(symbol, [])
        if len(held) >= limit:
            continue
        held.append({
            "as_of": row["as_of"], "source": row["source"], "reason": row["reason"],
            "detail": row["detail"], "magnitude": row["magnitude"],
            "url": row["url"],
            # The desk marks a reading it believes is a corporate action rather
            # than a real move. Carried through so the site can say so too.
            "suspect": "⚠" in (row["detail"] or ""),
            "track": tracks.get((row["source"].upper(), row["reason"].upper())),
        })
    return out
