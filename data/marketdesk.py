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

    conn.execute(
        "INSERT OR REPLACE INTO desk_runs"
        "(as_of, generated_at, schema_version, universe_size, stage_status, fetched_at)"
        " VALUES (?,?,?,?,?,?)",
        (stamp, str(payload.get("generated_at_utc") or ""), version,
         payload.get("universe_size"), json.dumps(stage_status), now))
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
    """The most recent desk signals per symbol, newest run first."""
    wanted = {s.upper() for s in symbols}
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
        })
    return out
