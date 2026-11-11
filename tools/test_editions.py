"""Offline checks on the back issues: tonight's edition is kept, earlier
sessions are rebuilt from the breadth history, and nothing kept on the night
is overwritten by a rebuild.

Run: python tools/test_editions.py
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from publish import editions  # noqa: E402

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:62} {got!r}")
    if not ok:
        failures.append(label)


def tree(root: pathlib.Path, as_of: str, days: list[str], above50: list[float]) -> None:
    def card(key, label, values, unit="percent"):
        return {"key": key, "label": label, "unit": unit, "value": values[-1],
                "series": [{"date": d, "value": v} for d, v in zip(days, values)]}
    (root / "market").mkdir(parents=True, exist_ok=True)
    (root / "meta.json").write_text(json.dumps({
        "as_of": as_of, "universe_count": 500,
        "screens": [{"key": "vcp", "name": "VCP", "total": 12}]}))
    (root / "breadth.json").write_text(json.dumps({"as_of": as_of, "cards": [
        card("breakouts", "Broke out today", [20, 4, 10], "count"),
        card("failed_pokes", "Tested the pivot and failed", [5, 30, 10], "count"),
        card("above_50ma", "Above the 50-day line", above50),
        card("confirmed_uptrend", "In a confirmed uptrend", [50.0, 20.0, 30.0])]}))
    (root / "indexes.json").write_text(json.dumps({
        "rows": [{"symbol": "SPY", "close": 110.0, "vs_200_pct": 8.0, "above_200": True}],
        "regime": {"symbol": "SPY", "above": True, "vs_200_pct": 8.0,
                   "note": "SPY is 8.0% above its 200-day average."}}))
    (root / "market" / "barcode.json").write_text(json.dumps({
        "n": 400, "counts": {"3": 200}, "labels": {"3": "Above both lines"},
        "healthy_by_tenth": [90, 80, 70, 60, 50, 40, 30, 20, 10, 0]}))


conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE bars(symbol TEXT, date TEXT, close REAL)")
conn.executescript((pathlib.Path(__file__).resolve().parent.parent
                    / "data" / "migrations" / "014_editions.sql").read_text())
# 260 sessions of a benchmark that rises a little each day: above its average.
import datetime as dt  # noqa: E402
start = dt.date(2026, 1, 1)
sessions = [(start + dt.timedelta(days=i)).isoformat() for i in range(260)]
conn.executemany("INSERT INTO bars VALUES ('SPY', ?, ?)",
                 [(d, 100 + i * 0.1) for i, d in enumerate(sessions)])
days = sessions[-3:]

with tempfile.TemporaryDirectory() as tmp:
    out = pathlib.Path(tmp)
    tree(out, days[-1], days, [70.0, 30.0, 50.0])
    written = editions.record(conn, out, "SPY")
    index = json.loads((out / "editions" / "index.json").read_text())
    check("tonight and the two sessions before it are in the archive", index["count"], 3)
    check("one file each, and the index", len(written), 4)
    check("newest first", [e["date"] for e in index["editions"]], days[::-1])
    check("tonight was kept, not rebuilt", index["editions"][0]["rebuilt"], False)
    check("earlier sessions are marked rebuilt", index["editions"][1]["rebuilt"], True)
    first = json.loads((out / "editions" / f"{days[0]}.json").read_text())
    check("a strong session rebuilds as in gear", first["headline"], "The tape is in gear")
    check("its four checks are all in gear", [c["score"] for c in first["meter"]], [1, 1, 1, 1])
    second = json.loads((out / "editions" / f"{days[1]}.json").read_text())
    check("failures at 1.5x breakouts score against", second["meter"][1]["score"], -1)
    check("a rebuilt edition carries no radar", "radar" in second, False)
    tonight = json.loads((out / "editions" / f"{days[-1]}.json").read_text())
    check("tonight keeps the breadth strip", tonight["tenths"][:3], [90, 80, 70])
    check("and the screen counts", tonight["screens"], [{"key": "vcp", "name": "VCP", "total": 12}])
    check("the newest has no newer edition", tonight["newer"], None)
    check("and points back to the one before", tonight["older"], days[1])

    # The next night: yesterday was kept in full and must not be replaced by
    # a rebuild from the breadth series.
    nxt = (dt.date.fromisoformat(days[-1]) + dt.timedelta(days=1)).isoformat()
    conn.execute("INSERT INTO bars VALUES ('SPY', ?, 126.0)", (nxt,))
    tree(out, nxt, days[1:] + [nxt], [30.0, 50.0, 60.0])
    editions.record(conn, out, "SPY")
    index = json.loads((out / "editions" / "index.json").read_text())
    check("a fourth edition the next night", index["count"], 4)
    kept = json.loads((out / "editions" / f"{days[-1]}.json").read_text())
    check("last night's full edition survives the next run", kept["rebuilt"], False)
    check("and now has a newer edition", kept["newer"], nxt)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL EDITION CHECKS PASS")
