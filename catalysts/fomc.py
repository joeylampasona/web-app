"""FOMC meeting dates: a hand-kept list, with an alarm on it.

Every other dated thing on this site comes from an API. This one does not,
because there is no free, stable API for the Fed's own calendar — scraping the
page works until they redesign it and then fails silently, which is the failure
mode this project spends most of its effort stamping out.

A hand-kept list has the opposite failure: it does not break, it just runs out,
and a calendar that has quietly run out looks exactly like a calendar with
nothing scheduled. So the list carries an expiry and the expiry is loud. When
the runway drops below WARN_BELOW_DAYS the nightly says so in its log, the
Discord summary says so, and the page says so. It is not possible for this to go
stale without somebody being told, which is the only thing that makes a
hand-kept list acceptable here.

FILLING IT IN
-------------
The Fed publishes meeting dates about two years ahead at

    https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

Each meeting runs one or two days; the decision lands on the LAST day, which is
the date that matters and the date to put here. Add them in order, oldest first:

    MEETINGS = [
        ("<yyyy-mm-dd>", "FOMC decision"),
        ("<yyyy-mm-dd>", "FOMC decision, projections"),
        ...
    ]

Real dates are deliberately not written here, not even as an example: a plausible
date sitting in a docstring is the sort of thing that gets copied into the list
by someone in a hurry, and a wrong FOMC date on a page traders read is worse than
an empty tab. Every date in MEETINGS should have been read off the Fed's page by
a person, that day.

Mark the four meetings with a Summary of Economic Projections — the Fed labels
them on that page — since those carry more weight than the others. Then set
CHECKED_ON to the day you copied them. That date is shown on the site, so a
reader can see how old the list is rather than trusting it blindly.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# Where these came from, shown on the page so the claim is checkable.
SOURCE = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

# The day somebody last copied the list from that page. Not a guess: set it when
# you edit MEETINGS and leave it alone otherwise.
CHECKED_ON = "2026-09-16"

# Decision days, oldest first. See FILLING IT IN above.
#
# Transcribed from the Fed's published schedule on the date in CHECKED_ON. Each
# entry is the SECOND day of a two-day meeting, which is when the decision lands.
# Every one falls on a Wednesday after a Tuesday, which is the FOMC's pattern and
# was checked rather than assumed.
#
# The 2027 meetings carry the Fed's asterisk for a Summary of Economic
# Projections — March, June, September, December, the usual four. The 2026 rows
# are not marked because the schedule they were copied from did not mark them.
MEETINGS: list[tuple[str, str]] = [
    ("2026-01-28", "FOMC decision"),
    ("2026-03-18", "FOMC decision"),
    ("2026-04-29", "FOMC decision"),
    ("2026-06-17", "FOMC decision"),
    ("2026-07-29", "FOMC decision"),
    ("2026-09-16", "FOMC decision"),
    ("2026-10-28", "FOMC decision"),
    ("2026-12-09", "FOMC decision"),
    ("2027-01-27", "FOMC decision"),
    ("2027-03-17", "FOMC decision, projections"),
    ("2027-04-28", "FOMC decision"),
    ("2027-06-09", "FOMC decision, projections"),
    ("2027-07-28", "FOMC decision"),
    ("2027-09-15", "FOMC decision, projections"),
    ("2027-10-27", "FOMC decision"),
    ("2027-12-08", "FOMC decision, projections"),
]

# Below this much runway the list needs topping up. A quarter is enough notice:
# the Fed publishes two years ahead, so this should never actually fire unless
# the list has been left alone for well over a year.
WARN_BELOW_DAYS = 120


@dataclass
class Meeting:
    date: dt.date
    label: str

    def to_json(self, as_of: dt.date) -> dict:
        return {
            "date": self.date.isoformat(),
            "label": self.label,
            "days_until": (self.date - as_of).days,
        }


def meetings(as_of: dt.date, lookahead_days: int = 90) -> list[Meeting]:
    """Listed meetings falling inside the window."""
    horizon = as_of + dt.timedelta(days=lookahead_days)
    out: list[Meeting] = []
    for raw, label in MEETINGS:
        try:
            day = dt.date.fromisoformat(raw)
        except ValueError:
            continue                      # a typo costs one meeting, not the run
        if as_of <= day <= horizon:
            out.append(Meeting(day, label))
    return sorted(out, key=lambda m: m.date)


def _parsed() -> list[dt.date]:
    """Only the dates that are actually dates. A typo costs one meeting."""
    days = []
    for raw, _ in MEETINGS:
        try:
            days.append(dt.date.fromisoformat(raw))
        except ValueError:
            continue
    return days


def runway_days(as_of: dt.date) -> int | None:
    """Days of calendar left. None when nothing parses."""
    days = _parsed()
    return (max(days) - as_of).days if days else None


def status(as_of: dt.date) -> dict:
    """Everything needed to shout about this list, in one place."""
    runway = runway_days(as_of)
    if runway is None:
        return {
            "stale": True, "runway_days": None, "checked_on": CHECKED_ON,
            "source": SOURCE, "listed": 0,
            "message": "No FOMC dates are loaded. The calendar shows data "
                       "releases only until somebody copies them from the Fed's "
                       "published schedule into catalysts/fomc.py.",
        }
    stale = runway < WARN_BELOW_DAYS
    return {
        "stale": stale, "runway_days": runway, "checked_on": CHECKED_ON,
        "source": SOURCE, "listed": len(_parsed()),
        "message": (
            f"The FOMC list runs out in {runway} days — the last meeting on it is "
            f"{max(_parsed())}. Top it up from the Fed's schedule; see "
            f"catalysts/fomc.py."
            if stale else
            f"{len(_parsed())} FOMC dates listed, running {runway} days out."
        ),
    }
