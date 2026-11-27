"""Offline: the market holiday calendar, and the nightly gate's copy of it.

    python tools/test_calendar.py
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import market_calendar as cal          # noqa: E402
from publish import discord                       # noqa: E402

FAILED: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:<64} {got!r}"
          + ("" if ok else f"   want {want!r}"))
    if not ok:
        FAILED.append(label)


D = dt.date.fromisoformat
WORKFLOW = (ROOT / ".github" / "workflows" / "nightly.yml").read_text()

print("The calendar:")
check("Thanksgiving is not a session", cal.is_session(D("2026-11-26")), False)
check("the half day after it is", cal.is_session(D("2026-11-27")), True)
check("the session before Thanksgiving's Friday", cal.previous_session(D("2026-11-26")), D("2026-11-25"))
check("the morning line after Wednesday is for Friday",
      discord.next_session(D("2026-11-25")), D("2026-11-27"))
check("after a Friday Christmas, Monday", cal.next_session(D("2026-12-24")), D("2026-12-28"))
check("Good Friday 2027 falls on 26 March", cal.is_session(D("2027-03-26")), False)
check("no holiday falls on a weekend", [d for d in cal.HOLIDAYS if d.weekday() >= 5], [])
check("ten closures a year", sorted({d.year: sum(1 for x in cal.HOLIDAYS if x.year == d.year)
                                     for d in cal.HOLIDAYS}.values()), [10, 10])

print("\nThe nightly gate's copy:")
found = re.search(r'holidays="([^"]*)"', WORKFLOW)
gate = {D(d) for d in found.group(1).split()} if found else set()
check("the gate lists exactly the calendar's dates", sorted(gate) == sorted(cal.HOLIDAYS), True)


def gate_session(now_utc: str) -> str:
    """Run the gate's own session lines with the clock set to `now_utc`."""
    block = WORKFLOW[WORKFLOW.index('holidays="'):WORKFLOW.index('echo "session=$session"')]
    script = "\n".join(line.strip() for line in block.splitlines())
    script = script.replace("$(TZ=America/New_York date +%F)",
                            f'$(TZ=America/New_York date -d "{now_utc}" +%F)')
    script = script.replace("$(TZ=America/New_York date +%-H)",
                            f'$(TZ=America/New_York date -d "{now_utc}" +%-H)')
    out = subprocess.run(["bash", "-c", script + '\necho "$session"'],
                         capture_output=True, text=True, env={**os.environ, "TZ": "UTC"})
    return out.stdout.strip()


check("1:42am ET the Friday after Thanksgiving: Wednesday's session",
      gate_session("2026-11-27 06:42 UTC"), "2026-11-25")
check("7pm ET on Thanksgiving: still Wednesday's",
      gate_session("2026-11-27 00:00 UTC"), "2026-11-25")
check("1:42am ET Saturday: Friday's half session",
      gate_session("2026-11-28 06:42 UTC"), "2026-11-27")
check("an ordinary Tuesday night: Tuesday",
      gate_session("2026-12-01 23:30 UTC"), "2026-12-01")

print()
if FAILED:
    print(f"{len(FAILED)} FAILED: {FAILED}")
    sys.exit(1)
print("ALL CALENDAR CHECKS PASS")
