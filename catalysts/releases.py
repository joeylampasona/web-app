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
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from data import settings

log = logging.getLogger(__name__)

BASE = "https://api.stlouisfed.org/fred"
API_KEY_NAME = "FRED_API_KEY"
# A paged walk asks for several thousand rows and FRED takes its time over
# the later offsets. Thirty seconds was enough for one page and not for six.
TIMEOUT = 90
RETRY_PAUSE = 3

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


# FRED states the shape it requires, and rejects anything else with a 400
# before looking at the request. Checking it here turns a silent empty calendar
# into a sentence naming the problem.
KEY_SHAPE = re.compile(r"^[0-9a-f]{32}$")


def key_problem() -> str:
    """Why the configured key cannot work, or "" if it looks usable."""
    key = settings.env(API_KEY_NAME)
    if not key:
        return f"{API_KEY_NAME} is not set"
    if not KEY_SHAPE.match(key):
        # Never the key itself, and never a prefix of it: this string goes to
        # the run log, which is public on a public repo.
        return (f"{API_KEY_NAME} is {len(key)} characters and FRED requires 32 "
                f"lower-case letters and digits. Re-copy it from "
                f"fredaccount.stlouisfed.org/apikey and re-save the secret, "
                f"taking care not to include a trailing space or newline.")
    return ""


def configured() -> bool:
    """True only when the key could actually work.

    This used to be `bool(key)`, so a malformed key published
    `configured: true` beside an empty calendar — the site reporting itself
    healthy while the section it describes had nothing in it.
    """
    return not key_problem()


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
    except urllib.error.HTTPError as exc:
        # FRED answers a rejected request with a body naming the parameter it
        # disliked. Discarding it left the nightly saying only "HTTP Error 400:
        # Bad Request" — true, useless, and indistinguishable from FRED being
        # down. The key is never in the message: it is in the query string, and
        # the query string is not what gets reported.
        detail = ""
        try:
            body = exc.read().decode()[:400]
            detail = f" — {body}" if body else ""
        except Exception:                          # noqa: BLE001
            pass
        raise ReleasesUnavailable(f"HTTP {exc.code}{detail}") from exc
    except Exception as exc:                      # noqa: BLE001
        raise ReleasesUnavailable(str(exc)) from exc


# FRED caps a page at 1000 rows and pages the rest by offset. One page looked
# like plenty — until the calendar was checked against its own horizon. Asked
# for 90 days and sorted ascending, the first page reached 2026-10-27 and
# stopped: seven weeks of the window, all of November and December, simply
# absent. Nothing in the response says a page was truncated; the count just
# happens to be exactly the limit, which is the only tell.
PAGE = 1000
MAX_PAGES = 8


def _page(start: dt.date, offset: int) -> dict:
    """One page, retried once. FRED is occasionally slow rather than down."""
    params = {
        "include_release_dates_with_no_data": "true",
        "realtime_start": start.isoformat(),
        "sort_order": "asc",
        "limit": PAGE,
        "offset": offset,
    }
    try:
        return _get("/releases/dates", params)
    except ReleasesUnavailable:
        time.sleep(RETRY_PAUSE)
        return _get("/releases/dates", params)


def _all_release_dates(start: dt.date, notice=None) -> list[dict]:
    """Every scheduled release date from `start`, across pages.

    A page that fails ends the walk but keeps what came before it. The first
    version raised straight out of the loop, so one slow page threw away every
    page already in hand: the run that introduced this printed "Data releases
    skipped: The read operation timed out" and published the previous night's
    truncated calendar, with the pagination it was testing never exercised.
    Nine hundred good rows are worth more than none.
    """
    rows: list[dict] = []
    for page in range(MAX_PAGES):
        try:
            payload = _page(start, page * PAGE)
        except ReleasesUnavailable as exc:
            if not rows:
                raise                       # nothing salvaged; the caller decides
            if notice:
                notice(f"Data releases: kept {len(rows):,} rows; page "
                       f"{page + 1} failed ({exc}).")
            return rows
        batch = payload.get("release_dates") or []
        rows.extend(batch)
        # A short page is the last page. FRED also reports the total, so a
        # truncation that this loop cannot reach is worth saying out loud
        # rather than publishing quietly.
        if len(batch) < PAGE:
            return rows
        total = int(payload.get("count") or 0)
        if total and len(rows) >= total:
            return rows
    if notice:
        notice(f"Data releases: stopped at {len(rows):,} rows after "
               f"{MAX_PAGES} pages; the calendar may be short at its far end.")
    return rows


def fetch(as_of: dt.date, lookahead_days: int | None = None,
          notice=None) -> list[Release]:
    """Scheduled releases from `as_of` forward. Empty when unavailable."""
    problem = key_problem()
    if problem:
        if notice:
            notice(f"Data releases skipped: {problem}")
        return []
    horizon = as_of + dt.timedelta(
        days=int(lookahead_days or settings.get("catalysts.lookahead_days", 90)))
    try:
        # The realtime window is about VINTAGES — which edition of the data we
        # are asking to see — not about which release dates to return. It was
        # being set to (as_of, as_of + 90 days), which asks for a vintage of
        # the data as it will exist three months from now. FRED rejects that
        # with a 400, and the whole calendar has been silently empty since.
        #
        # The schedule ahead comes from include_release_dates_with_no_data,
        # not from the realtime window: future dates have nothing published
        # against them yet, so without that flag the endpoint answers with
        # history only. The horizon is applied below, where it belongs.
        today = min(as_of, dt.date.today())
        rows = _all_release_dates(today, notice)
    except ReleasesUnavailable as exc:
        if notice:
            notice(f"Data releases skipped: {exc}")
        return []

    out: list[Release] = []
    for row in rows:
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
        if not out:
            # FRED schedules something most weekdays, so an empty answer over a
            # ninety-day horizon is a fault wearing a quiet calendar's clothes.
            # The last version of this published `configured: true, count: 0`
            # without a word, and it stayed that way until somebody happened to
            # look at the file.
            notice(f"FRED answered with no scheduled releases at all between "
                   f"{as_of} and {horizon}. That is not a quiet calendar — it "
                   f"publishes something most weekdays — so treat this as a "
                   f"broken request rather than an empty one.")
        else:
            # The date the calendar actually reaches, not the one it asked for.
            # This said "to {horizon}" regardless, so a feed truncated seven
            # weeks short of the window reported the full window and looked
            # correct. Saying the real last date makes a short answer visible
            # in the one place somebody reads every night.
            reached = max(r.date for r in out)
            short = ("" if reached >= horizon
                     else f" — short of the {horizon} horizon, so the far end "
                          f"of the window is missing")
            notice(f"{len(out):,} scheduled data releases to {reached} "
                   f"({flagged:,} of them widely watched){short}.")
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


# ------------------------------------------------------- the two that matter
#
# FRED lists a release only a few weeks ahead. Market Desk found it on
# 2026-11-26: asked for the year, it held one date each for CPI and the jobs
# report, the December ones, though the Bureau of Labor Statistics had already
# published all of 2027. A calendar built from FRED alone showed the next CPI
# and nothing after it, and the week ahead could not say a print was coming
# until the week it came.
#
# So the two releases that move markets most are kept here as well, from the
# BLS's own schedule pages (bls.gov/schedule/news_release/cpi.htm and
# empsit.htm, read 26 November 2026; the same dates Market Desk keeps). FRED
# still wins on any date it has: it hears first when a release is moved, which
# a government shutdown does. These fill the dates FRED does not list yet.
# Extend each December, when the BLS posts the next year.
BLS_SCHEDULE = {
    # FRED's own release ids, so a filled date links to the same page.
    "Consumer Price Index": (10, (
        "2026-12-10",
        "2027-01-13", "2027-02-11", "2027-03-10", "2027-04-13", "2027-05-12",
        "2027-06-10", "2027-07-14", "2027-08-11", "2027-09-14", "2027-10-14",
        "2027-11-10", "2027-12-10")),
    "Employment Situation": (50, (
        "2026-12-04",
        "2027-01-08", "2027-02-05", "2027-03-05", "2027-04-02", "2027-05-07",
        "2027-06-04", "2027-07-02", "2027-08-06", "2027-09-03", "2027-10-08",
        "2027-11-05", "2027-12-03")),
}


def schedule_runs_out() -> dt.date:
    """The last date the kept schedule covers, for the nightly to warn on."""
    return min(dt.date.fromisoformat(dates[-1]) for _, dates in BLS_SCHEDULE.values())


def with_schedule(found: list[Release], as_of: dt.date, horizon: dt.date) -> list[Release]:
    """FRED's releases with the kept CPI and jobs dates added where FRED has
    no release of that name within a week of the date. A date FRED moved
    stays FRED's; the kept one is not added beside it."""
    out = list(found)
    for name, (release_id, dates) in BLS_SCHEDULE.items():
        theirs = [r.date for r in found if r.name.lower() == name.lower()]
        for text in dates:
            day = dt.date.fromisoformat(text)
            if not as_of <= day <= horizon:
                continue
            if any(abs((day - known).days) <= 7 for known in theirs):
                continue
            out.append(Release(date=day, release_id=release_id, name=name, notable=True))
    out.sort(key=lambda r: (r.date, not r.notable, r.name))
    return out


def load(conn, as_of: dt.date, lookahead_days: int | None = None) -> list[Release]:
    horizon = as_of + dt.timedelta(
        days=int(lookahead_days or settings.get("catalysts.lookahead_days", 90)))
    rows = conn.execute(
        "SELECT date, release_id, name, notable FROM econ_releases"
        " WHERE date >= ? AND date <= ? ORDER BY date, notable DESC, name",
        (as_of.isoformat(), horizon.isoformat())).fetchall()
    found = [Release(dt.date.fromisoformat(r["date"]), r["release_id"],
                     r["name"], bool(r["notable"])) for r in rows]
    return with_schedule(found, as_of, horizon)


def prune(conn, before: dt.date) -> int:
    """Releases whose date has passed are history, and this is a calendar."""
    cursor = conn.execute("DELETE FROM econ_releases WHERE date < ?",
                          (before.isoformat(),))
    conn.commit()
    return cursor.rowcount or 0
