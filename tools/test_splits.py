"""Offline checks on split adjustment of stored bars (data/splits.py).

Run: python tools/test_splits.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from data import splits  # noqa: E402

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:58} {got!r}")
    if not ok:
        failures.append(label)


conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.executescript("""
CREATE TABLE bars(symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
                  volume REAL, PRIMARY KEY(symbol, date));
CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT);
""" + (pathlib.Path(__file__).resolve().parent.parent
       / "data/migrations/013_splits_applied.sql").read_text())

D = dt.date.fromisoformat
days = [D("2026-10-01") + dt.timedelta(days=i) for i in range(20)]
SPLIT = days[10]


def fill(symbol: str, before: float, after: float) -> None:
    for i, d in enumerate(days):
        px = before if i < 10 else after
        conn.execute("INSERT INTO bars VALUES (?,?,?,?,?,?,?)",
                     (symbol, d.isoformat(), px, px + 1, px - 1, px, 1000.0))


fill("UNADJ", 300.0, 102.0)      # 3-for-1, cached before it: needs adjusting
fill("DONE", 100.0, 102.0)       # 3-for-1, fetched after it: already right
fill("REV", 2.0, 19.5)           # 1-for-10 reverse, unadjusted
fill("SMALL", 100.0, 80.0)       # 5-for-4: too small to tell from a bad day
fill("LATE", 300.0, 300.0)       # executes tomorrow: no bar after it yet


class Fake:
    def _get(self, path, params=None):
        return {"results": [
            {"ticker": "UNADJ", "execution_date": SPLIT.isoformat(), "split_from": 1, "split_to": 3},
            {"ticker": "DONE", "execution_date": SPLIT.isoformat(), "split_from": 1, "split_to": 3},
            {"ticker": "REV", "execution_date": SPLIT.isoformat(), "split_from": 10, "split_to": 1},
            {"ticker": "SMALL", "execution_date": SPLIT.isoformat(), "split_from": 4, "split_to": 5},
            {"ticker": "LATE", "execution_date": "2026-10-25", "split_from": 1, "split_to": 2},
            {"ticker": "GONE", "execution_date": SPLIT.isoformat(), "split_from": 1, "split_to": 2},
        ]}


def close(symbol: str, i: int) -> float:
    return round(conn.execute("SELECT close FROM bars WHERE symbol=? AND date=?",
                              (symbol, days[i].isoformat())).fetchone()[0], 4)


dry = splits.apply(conn, Fake(), days[-1], dry_run=True)
check("a dry run reports the adjustment", [a["symbol"] for a in dry["adjusted"]], ["REV", "UNADJ"])
check("and changes nothing", close("UNADJ", 0), 300.0)

out = splits.apply(conn, Fake(), days[-1])
check("unadjusted bars before a 3-for-1 are divided by three", close("UNADJ", 0), 100.0)
check("bars from the split on are untouched", close("UNADJ", 10), 102.0)
check("volume goes the other way", conn.execute(
    "SELECT volume FROM bars WHERE symbol='UNADJ' AND date=?", (days[0].isoformat(),)).fetchone()[0], 3000.0)
check("bars already adjusted are left alone", close("DONE", 0), 100.0)
check("a reverse split multiplies", close("REV", 0), 20.0)
check("a split under 3-for-2 is not guessed at", close("SMALL", 0), 100.0)
check("counts", (out["adjusted"] and len(out["adjusted"]), out["already_adjusted"],
                 out["too_small"], out["pending"], out["no_bars"]), (2, 1, 1, 1, 1))
again = splits.apply(conn, Fake(), days[-1])
check("a second run adjusts nothing more", (len(again["adjusted"]), close("UNADJ", 0)), (0, 100.0))
check("a split not settled yet is asked about again", again["pending"], 1)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL SPLIT CHECKS PASS")
