"""What each source did tonight, kept so the edition can say so.

Two sources failed in one week in November 2026 and neither said anything.
The quote host refused every request for a session; the option-chain host
did the same and the nightly quietly fell back to a shorter book; and the
Market Desk stopped publishing while the site carried on with its last file.
Each was visible only to someone reading a thousand-line log for the absence
of a line.

So every stage that reaches the network records one row here: how many it
asked about, how many answered, and a sentence. Publish reads them back,
adds the two it can judge for itself, and writes the lot into meta.json. The
log, the Discord summary and the colophon page all read that one list.

Stages run as separate processes, so the rows live in the database's
key-value table rather than in memory.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from data import store

PREFIX = "health."

#: Below this share answered, a source is reported as partial.
PARTIAL_BELOW = 0.8

#: The order the rows are published in, and what each is called.
SOURCES = (
    ("prices", "Prices", "Polygon"),
    ("options", "Option chains", "Cboe, then OCC with Yahoo"),
    ("earnings_dates", "Earnings dates", "Yahoo"),
    ("forecasts", "Analyst forecasts", "Yahoo"),
    ("filings", "Company filings", "SEC"),
    ("desk", "Market Desk", "Market Desk nightly"),
    ("news", "Headlines", "Polygon"),
)

_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven",
          "eight", "nine", "ten")


def judge(asked, answered) -> str:
    """ok, partial or down, from how many of those asked gave an answer."""
    if asked is None or answered is None or asked <= 0:
        return "ok"
    if answered <= 0:
        return "down"
    return "partial" if answered / asked < PARTIAL_BELOW else "ok"


def record(conn, key: str, session: dt.date | None, detail: str, *,
           asked: int | None = None, answered: int | None = None,
           status: str | None = None) -> dict:
    """Keep one source's row for tonight. `status` overrides the ratio."""
    row = {
        "session": session.isoformat() if session else None,
        "asked": asked,
        "answered": answered,
        "status": status or judge(asked, answered),
        "detail": detail.strip(),
        "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    store.set_kv(conn, PREFIX + key, json.dumps(row, separators=(",", ":")))
    return row


def counted(sentence: str) -> tuple[int | None, int | None]:
    """(answered, asked) from a stage's own "N of M" sentence, if it has one."""
    found = re.search(r"([\d,]+) of ([\d,]+)", sentence or "")
    if not found:
        return None, None
    return int(found[1].replace(",", "")), int(found[2].replace(",", ""))


class Listener:
    """Passes a stage's notices through and keeps the ones asked for.

    The stages already say what happened, in a sentence, as they go. Rather
    than thread a second return value through each of them, this listens for
    the sentence that is the stage's summary and keeps it word for word.
    """

    def __init__(self, emit) -> None:
        self.emit = emit
        self.kept: dict[str, str] = {}
        self.watch: list[tuple[str, str]] = []

    def keep(self, key: str, containing: str) -> "Listener":
        self.watch.append((key, containing))
        return self

    def __call__(self, message: str) -> None:
        self.emit(message)
        for key, containing in self.watch:
            # The first one wins: a stage that runs twice in a night asks
            # about less the second time, and the first is the real tally.
            if containing in message and key not in self.kept:
                self.kept[key] = message


def _sessions_between(conn, earlier: str, later: str) -> int | None:
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT date) FROM bars WHERE date > ? AND date <= ?",
            (earlier, later)).fetchone()
        return int(row[0])
    except Exception:                               # noqa: BLE001
        return None


def _count(n: int) -> str:
    return _WORDS[n] if 0 <= n < len(_WORDS) else f"{n:,}"


def report(conn, session: dt.date, desk_run: dict | None = None,
           provider: str = "") -> list[dict]:
    """Tonight's rows, in publishing order. Sources with nothing recorded and
    nothing to judge are left out rather than guessed at."""
    as_of = session.isoformat()
    rows: dict[str, dict] = {}

    for key, _, _ in SOURCES:
        raw = store.get_kv(conn, PREFIX + key, "")
        if not raw:
            continue
        try:
            kept = json.loads(raw)
        except ValueError:
            continue
        row = {"status": kept.get("status") or "ok",
               "detail": kept.get("detail") or "",
               "as_of": kept.get("session")}
        if kept.get("session") and kept["session"] < as_of:
            # The stage did not run for this session, so what it said is about
            # an earlier one and everything it feeds is carried over.
            row["status"] = "behind"
            row["detail"] = (f"Not refreshed for this edition; last read for "
                             f"{kept['session']}. {row['detail']}").strip()
        rows[key] = row

    # Prices are judged from what is stored: the bars are the edition.
    try:
        bars = int(conn.execute("SELECT COUNT(*) FROM bars WHERE date = ?",
                                (as_of,)).fetchone()[0])
        rows["prices"] = {
            "status": "ok" if bars else "down",
            "detail": (f"{bars:,} daily bars for {as_of}." if bars
                       else f"No bars stored for {as_of}."),
            "as_of": as_of,
        }
    except Exception:                               # noqa: BLE001
        pass

    # The desk is judged by the date of its newest run against the session.
    if desk_run and desk_run.get("as_of"):
        covers = str(desk_run["as_of"])
        behind = _sessions_between(conn, covers, as_of) if covers < as_of else 0
        failed = sorted(name for name, state in (desk_run.get("stage_status") or {}).items()
                        if str(state).lower() not in ("ok", "success", "done"))
        if behind is None:
            detail, status = f"Last run covers {covers}.", "ok"
        elif behind <= 1:
            # One behind is the ordinary state: the desk finishes its night
            # after this edition has gone out.
            detail = (f"Last run covers {covers}, the same session as this edition."
                      if behind == 0 else
                      f"Last run covers {covers}, one session before this edition.")
            status = "ok"
        else:
            detail = (f"Last run covers {covers}, {_count(behind)} sessions before "
                      f"this edition.")
            status = "behind"
        if failed:
            detail += f" Stages not reporting ok: {', '.join(failed)}."
            status = "partial" if status == "ok" else status
        rows["desk"] = {"status": status, "detail": detail, "as_of": covers}

    out = []
    for key, label, origin in SOURCES:
        if key not in rows:
            continue
        if key in ("prices", "news") and provider:
            origin = provider.capitalize()
        out.append({"key": key, "label": label, "from": origin, **rows[key]})
    return out


def summary(rows: list[dict]) -> list[str]:
    """One line per source that is not ok, for a log or a message."""
    return [f"{row['label']} ({row['status']}): {row['detail']}"
            for row in rows if row.get("status") != "ok"]
