"""Offline checks on the strength radar, the leadership layers and the nights
on each screen.

Run: python tools/test_radar.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from patterns import scan  # noqa: E402
from rankings import leadership, radar  # noqa: E402

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:60} {got!r}")
    if not ok:
        failures.append(label)


# ---- the radar's readings
days = [dt.date(2025, 1, 1) + dt.timedelta(days=i) for i in range(300)]
flat = {d: 100.0 for d in days}
rising = {d: 100.0 * (1.001 ** i) for i, d in enumerate(days)}
r = radar.readings(rising, flat, (0, 5))
check("ratio change over 21 sessions", r[0]["rs21"], round((1.001 ** 21 - 1) * 100, 2))
check("a steadily rising ratio is fully aligned", radar.aligned(r[0]), "full")
check("a falling ratio is not aligned",
      radar.aligned(radar.readings(flat, rising, (0,))[0]), "none")
check("the week ago is five sessions back", r[5]["date"], days[-6].isoformat())
short = {d: v for d, v in list(rising.items())[-100:]}
check("too short for 126 sessions reads as missing, not zero",
      radar.readings(short, flat, (0,))[0]["rs126"], None)
check("and its trend cannot be called", radar.aligned(radar.readings(short, flat, (0,))[0]), None)

pairs = {"QQQ/SPY": {"now": {"rs126": 5.0, "rs21": 1.0}, "start": {"rs126": 4.0}},
         "RSP/SPY": {"now": {"rs126": -2.0, "rs21": -1.0}, "start": {"rs126": -2.0}},
         "IWM/QQQ": {"now": {"rs126": -6.0}, "start": {"rs126": -5.0}},
         "IWM/SPY": {"now": {"rs126": -1.0}, "start": {"rs126": -1.0}}}
b = {"n": 20, "full": 3, "pos126": 6, "pos21": 8, "pos63": 7}
check("growth ahead with few groups aligned is narrow leadership",
      radar.classify(pairs, b, b, 0.5)["label"], "Narrow growth leadership")
broad = {"n": 20, "full": 10, "pos126": 12, "pos21": 12, "pos63": 12}
pairs_broad = dict(pairs, **{"RSP/SPY": {"now": {"rs126": 1.0, "rs21": 0.5},
                                          "start": {"rs126": 0.5}}})
check("equal weight ahead with most groups aligned is a broad advance",
      radar.classify(pairs_broad, broad, broad, 1.0)["label"], "Broad advance")

# ---- the layers
full_pos = {"aligned": "full", "pos126": True}
weak = {"aligned": "none", "pos126": False}
check("ahead everywhere in a leading industry", leadership.layer({21: 2, 63: 3, 126: 4}, full_pos), "front")
check("ahead everywhere in a lagging industry", leadership.layer({21: 2, 63: 3, 126: 4}, weak), "specific")
check("behind at one and six months in a leading industry",
      leadership.layer({21: -2, 63: 1, 126: -4}, full_pos), "weak_in_strong")
check("behind over six months, ahead lately", leadership.layer({21: 2, 63: 3, 126: -4}, weak), "turning")
check("behind everywhere in a lagging industry", leadership.layer({21: -2, 63: -3, 126: -4}, weak), "caution")
check("no industry index: cannot be front line",
      leadership.layer({21: 2, 63: 3, 126: 4}, None), "unconfirmed")
check("no one-month reading", leadership.layer({21: None, 63: 3, 126: 4}, full_pos), "unconfirmed")


# ---- nights on a screen
class Row:
    def __init__(self, symbol):
        self.symbol = symbol


conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.execute("CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT)")


def night(day: str, names: list[str]) -> dict:
    result = scan.ScanResult(as_of=dt.date.fromisoformat(day),
                             screens={"vcp": [Row(n) for n in names]})
    return scan.nights(conn, result)["vcp"]


first = night("2026-11-02", ["AAA", "BBB"])
check("first night: one session in the window", first["AAA"], {"run": 1, "of": 1, "window": 1})
night("2026-11-03", ["AAA"])
third = night("2026-11-04", ["AAA", "BBB", "CCC"])
check("three nights running", third["AAA"], {"run": 3, "of": 3, "window": 3})
check("back after a night off", third["BBB"], {"run": 1, "of": 2, "window": 3})
check("new to the screen", third["CCC"], {"run": 1, "of": 1, "window": 3})
again = night("2026-11-04", ["AAA", "BBB"])
check("the same session rescanned counts once", again["AAA"], {"run": 3, "of": 3, "window": 3})
check("a name gone on the rescan is not counted", "CCC" in again, False)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL RADAR CHECKS PASS")
