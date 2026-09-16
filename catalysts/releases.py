"""Scheduled economic data releases, from FRED.

Deliberately not called an economic calendar. FRED publishes when *data* comes
out — CPI, the employment situation, GDP — and says nothing about when the Fed
meets. FOMC dates come from somewhere else entirely and are not in here, so the
page says "Data releases" rather than promising a calendar it does not have.

FRED lists several hundred releases, most of them obscure. Everything it returns
is kept, because deciding what matters is not ours to do silently, but a handful
of names that move markets are flagged so a reader is not made to find the CPI
print among two hundred regional surveys. The flag is matched on the release's
name rather than its numeric id: a name is legible in the output and checkable
by eye, and if FRED renames something the release simply stops being flagged —
it does not vanish. A missing flag costs an ordering; a missing release would
cost the fact.

Degrades to nothing on any failure, like every other optional source here. A
missing calendar costs a tab; a raised exception costs the nightly run.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass

from data import settings

log = logging.getLogger(__name__)

BASE = "https://api.stlouisfed.org/fred"
API_KEY_NAME = "FRED_API_KEY"
TIMEOUT = 30

# Substrings, lowercased, matched against the release name. Not a curated
# calendar — the dates all come from FRED either way. This only decides what a
# reader sees first.
NOTABLE = (
    "employment situation",
    "consumer price index",
    "producer price index",
    "gross domestic product",
    "personal income and outlays",
    "retail sales",
    "job openings",
    "industrial production",
    "housing starts",
    "consumer sentiment",
    "consumer confidence",
    "durable goods",
    "gdp",
    "unemployment insurance weekly claims",
    "advance monthly sales",
)


class ReleasesUnavailable(RuntimeError):
    """FRED could not be reached or refused us."""


@dataclass
class Release:
    date: dt.date
    release_id: int
    name: str
    notable: bool

    def to_json(self, as_of: dt.date) -> dict:
        return {
            "date": self.date.isoformat(),
            "release_id": self.release_id,
            "name": self.name,
            "notable": self.notable,
            "days_until": (self.date - as_of).days,
            # No id, no link: rid=0 is a page that does not exist, and a link
            # that goes nowhere is worse than no link.
            "link": (f"https://fred.stlouisfed.org/release?rid={self.release_id}"
                     if self.release_id else None),
        }


def configured() -> bool:
    return bool(settings.env(API_KEY_NAME))


def _get(path: str, params: dict) -> dict:
    key = settings.env(API_KEY_NAME)
    if not key:
        raise ReleasesUnavailable(f"{API_KEY_NAME} is not set")
    query = urllib.parse.urlencode({**params, "api_key": key, "file_type": "json"})
    request = urllib.request.Request(
        f"{BASE}{path}?{query}",
        # FRED is a public service run by a Reserve Bank. Name ourselves so a
        # problem on their side can be traced to a caller, the same reason the
        # SEC requires it.
        headers={"User-Agent": "base-and-breakout/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except Exception as exc:                      # noqa: BLE001
        raise ReleasesUnavailable(str(exc)) from exc


def fetch(as_of: dt.date, lookahead_days: int | None = None,
          notice=None) -> list[Release]:
    """Scheduled releases from `as_of` forward. Empty when unavailable."""
    if not configured():
        if notice:
            notice("FRED not configured; data releases skipped.")
        return []
    horizon = as_of + dt.timedelta(
        days=int(lookahead_days or settings.get("catalysts.lookahead_days", 90)))
    try:
        payload = _get("/releases/dates", {
            # Future dates have no data attached to them yet, so without this
            # the endpoint answers with history only — which is the opposite of
            # a calendar.
            "include_release_dates_with_no_data": "true",
            "realtime_start": as_of.isoformat(),
            "realtime_end": horizon.isoformat(),
            "sort_order": "asc",
            "limit": 1000,
        })
    except ReleasesUnavailable as exc:
        if notice:
            notice(f"Data releases skipped: {exc}")
        return []

    out: list[Release] = []
    for row in payload.get("release_dates") or []:
        try:
            day = dt.date.fromisoformat(str(row["date"]))
        except (KeyError, TypeError, ValueError):
            continue
        # The endpoint's realtime window is about vintages, not the schedule, so
        # the range is enforced here rather than trusted.
        if day < as_of or day > horizon:
            continue
        name = str(row.get("release_name") or "").strip()
        if not name:
            continue
        lowered = name.lower()
        out.append(Release(
            date=day,
            release_id=int(row.get("release_id") or 0),
            name=name,
            notable=any(term in lowered for term in NOTABLE),
        ))

    out.sort(key=lambda r: (r.date, not r.notable, r.name))
    if notice:
        flagged = sum(1 for r in out if r.notable)
        notice(f"{len(out):,} scheduled data releases to {horizon} "
               f"({flagged:,} of them widely watched).")
    return out


# ---------------------------------------------------------------- storage
#
# The catalysts stage fetches; publish reads. Publish never reaches the network,
# so a rebuild of out/ cannot depend on FRED being up, and a day FRED is down
# keeps yesterday's schedule rather than losing the tab.

def store(conn, rows: list[Release]) -> int:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    written = 0
    for row in rows:
        conn.execute(
            "INSERT OR REPLACE INTO econ_releases"
            "(date, release_id, name, notable, fetched_at) VALUES (?,?,?,?,?)",
            (row.date.isoformat(), row.release_id, row.name,
             1 if row.notable else 0, now))
        written += 1
    conn.commit()
    return written


def load(conn, as_of: dt.date, lookahead_days: int | None = None) -> list[Release]:
    horizon = as_of + dt.timedelta(
        days=int(lookahead_days or settings.get("catalysts.lookahead_days", 90)))
    rows = conn.execute(
        "SELECT date, release_id, name, notable FROM econ_releases"
        " WHERE date >= ? AND date <= ? ORDER BY date, notable DESC, name",
        (as_of.isoformat(), horizon.isoformat())).fetchall()
    return [Release(dt.date.fromisoformat(r["date"]), r["release_id"],
                    r["name"], bool(r["notable"])) for r in rows]


def prune(conn, before: dt.date) -> int:
    """Releases whose date has passed are history, and this is a calendar."""
    cursor = conn.execute("DELETE FROM econ_releases WHERE date < ?",
                          (before.isoformat(),))
    conn.commit()
    return cursor.rowcount or 0
