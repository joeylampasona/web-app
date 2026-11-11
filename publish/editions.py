"""Back issues: each night's front page, kept and written out again.

The site only ever showed tonight. The data branch is rebuilt whole each
night, so the read a visitor saw on Tuesday could not be looked at again on
Wednesday, and nobody could check what the page had said before a move.

An edition is deliberately small: the read and the four checks behind it,
where strength sat, the leadership counts, the breadth strip in ten cells
and how many names each screen held. Nothing gated goes in: screen totals
are counts, and the only names are the front line's strongest, which the
leadership page already publishes.

Editions are stored in the database, since the published tree is not kept,
and every night the whole archive is written out from it.

The first night also rebuilds what it honestly can of the sessions before
it: the four checks are counts the breadth file keeps twenty sessions of,
and the benchmark's 200-day line is arithmetic on stored bars. Those rebuilt
editions carry the read and its checks and say plainly that the rest of the
night's page was not kept.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3
from typing import Any, Sequence

from digest import compose

KEEP = 260          # about a year of sessions
SMA = 200


def _read(out: pathlib.Path, name: str) -> Any | None:
    try:
        return json.loads((out / name).read_text())
    except (OSError, ValueError):
        return None


def snapshot(out: pathlib.Path) -> dict | None:
    """Tonight's edition, from the tree that was just published."""
    meta = _read(out, "meta.json") or {}
    as_of = meta.get("as_of")
    if not as_of:
        return None
    d = compose.build(out)
    cards = {c["key"]: c for c in (_read(out, "breadth.json") or {}).get("cards", [])}
    layers = _read(out, "market/leadership.json") or {}
    barcode = _read(out, "market/barcode.json") or {}
    return {
        "date": as_of,
        "headline": d.verdict,
        "blurb": d.verdict_blurb,
        "meter": d.meter,
        "checks": d.checks,
        "indexes": [{"symbol": r["symbol"], "close": r.get("close"),
                     "vs_200_pct": r.get("vs_200_pct"), "above_200": r.get("above_200")}
                    for r in d.indexes],
        "radar": d.radar,
        "layers": {"counts": layers.get("counts"), "order": layers.get("order"),
                   "labels": layers.get("labels"),
                   "front": [r["symbol"] for r in (layers.get("top") or {}).get("front", [])[:8]]}
                  if layers.get("counts") else None,
        "tenths": d.tenths,
        "barcode": {"n": barcode.get("n"), "counts": barcode.get("counts"),
                    "labels": barcode.get("labels")} if barcode.get("n") else None,
        "breadth": [{"key": k, "label": c["label"], "value": c["value"], "unit": c["unit"]}
                    for k, c in cards.items()],
        "screens": [{"key": s["key"], "name": s["name"], "total": s.get("total", 0)}
                    for s in meta.get("screens", [])],
        "universe": meta.get("universe_count"),
        "rebuilt": False,
    }


def _regime_on(closes: Sequence[tuple[str, float]], day: str, symbol: str) -> dict:
    """The benchmark against its 200-day average as of one past session."""
    upto = [c for d, c in closes if d <= day]
    if len(upto) < SMA or not any(d == day for d, _ in closes):
        return {"symbol": symbol, "above": None}
    average = sum(upto[-SMA:]) / SMA
    gap = round((upto[-1] / average - 1) * 100, 2)
    side = "above" if gap >= 0 else "below"
    return {"symbol": symbol, "above": gap >= 0, "vs_200_pct": gap,
            "note": f"{symbol} was {abs(gap):.1f}% {side} its 200-day average."}


def rebuild(conn: sqlite3.Connection, out: pathlib.Path, benchmark: str) -> int:
    """Editions for the sessions the breadth file still remembers and the
    archive does not hold. The read and its four checks only."""
    breadth = _read(out, "breadth.json") or {}
    cards = {c["key"]: c for c in breadth.get("cards", [])}
    as_of = breadth.get("as_of") or ""
    series = {k: {p["date"]: p["value"] for p in c.get("series", [])} for k, c in cards.items()}
    days = sorted(set().union(*[set(v) for v in series.values()]) if series else [])
    held = {r[0] for r in conn.execute("SELECT date FROM editions")}
    closes = [(r[0], r[1]) for r in conn.execute(
        "SELECT date, close FROM bars WHERE symbol=? AND close>0 ORDER BY date", (benchmark,))]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    made = 0
    for day in days:
        if day >= as_of or day in held:
            continue
        past = {"cards": [{"key": k, "value": v[day]} for k, v in series.items() if day in v]}
        verdict, blurb, checks, meter = compose._verdict(                 # noqa: SLF001
            past, {"regime": _regime_on(closes, day, benchmark)})
        if not meter:
            continue
        body = {"date": day, "headline": verdict, "blurb": blurb, "meter": meter,
                "checks": [c for c in checks if c],
                "breadth": [{"key": k, "label": cards[k]["label"], "value": v[day],
                             "unit": cards[k]["unit"]} for k, v in series.items() if day in v],
                "rebuilt": True}
        conn.execute("INSERT OR IGNORE INTO editions(date, body, rebuilt, written_at)"
                     " VALUES (?,?,1,?)", (day, json.dumps(body), now))
        made += 1
    conn.commit()
    return made


def record(conn: sqlite3.Connection, out: pathlib.Path, benchmark: str = "SPY") -> list[pathlib.Path]:
    """Keep tonight's edition, then write the archive out in full."""
    edition = snapshot(out)
    if edition is None:
        return []
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    conn.execute("INSERT OR REPLACE INTO editions(date, body, rebuilt, written_at)"
                 " VALUES (?,?,0,?)", (edition["date"], json.dumps(edition), now))
    conn.commit()
    rebuild(conn, out, benchmark)

    rows = [json.loads(r[0]) for r in conn.execute(
        "SELECT body FROM editions ORDER BY date DESC LIMIT ?", (KEEP,))]
    folder = out / "editions"
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for i, body in enumerate(rows):
        # Newest first, so the next edition is the one before it in the list.
        body["newer"] = rows[i - 1]["date"] if i > 0 else None
        body["older"] = rows[i + 1]["date"] if i + 1 < len(rows) else None
        path = folder / f"{body['date']}.json"
        path.write_text(json.dumps(body, separators=(",", ":")))
        written.append(path)
    index = {
        "as_of": edition["date"],
        "count": len(rows),
        "editions": [{
            "date": b["date"], "headline": b["headline"],
            "scores": [c["score"] for c in b.get("meter", [])],
            "label": (b.get("radar") or {}).get("label"),
            "front": ((b.get("layers") or {}).get("counts") or {}).get("front"),
            "breakouts": next((c["value"] for c in b.get("breadth", [])
                               if c["key"] == "breakouts"), None),
            "failed": next((c["value"] for c in b.get("breadth", [])
                            if c["key"] == "failed_pokes"), None),
            "rebuilt": bool(b.get("rebuilt")),
        } for b in rows],
    }
    path = folder / "index.json"
    path.write_text(json.dumps(index, separators=(",", ":")))
    written.append(path)
    return written
