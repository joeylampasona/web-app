"""The Market Strength Radar: where strength sits, read from price ratios.

Ported from Market Desk's scanners/radar.py. For each key relationship
(growth against the market, small caps against growth and against the
market, equal weight against the market) and for every sector and group ETF
against SPY, the ratio of closes is read over 21, 42, 63, 126 and 252
sessions, with three trend flags on the ratio itself: its 21-day mean above
its 63-day, 42 above 126, 63 above 126. All three is fully aligned; one or
two, partially; none, unaligned.

Market Desk logs every reading to a table so a week can be rebuilt. Here the
bars are all in the database, so the week ago is simply read again at an
offset of five sessions; nothing is stored.

On top of the readings: breadth across the groups per session, a sector map
(leaders, strong but cooling, improving most, weakest, lost most), one of five
fixed labels for the week with the numbers that produced it, and the
thresholds that would change it. Measured, never scored or forecast.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from data import settings
from data.market import Market
from data.types import Bar

WINDOWS = (21, 42, 63, 126, 252)
WEEK = 5
SPARK = 63

LABELS = {"XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
          "XLV": "Health care", "XLY": "Consumer discretionary",
          "XLP": "Consumer staples", "XLI": "Industrials", "XLB": "Materials",
          "XLU": "Utilities", "XLRE": "Real estate", "XLC": "Communication"}

DEFAULT_PAIRS = [("QQQ", "SPY", "Growth vs market"),
                 ("IWM", "QQQ", "Small caps vs growth"),
                 ("IWM", "SPY", "Small caps vs market"),
                 ("RSP", "SPY", "Equal weight vs market")]


def pairs() -> list[tuple[str, str, str]]:
    rows = settings.get("rankings.radar_pairs") or DEFAULT_PAIRS
    return [(str(a), str(b), str(label)) for a, b, label in rows]


def groups() -> list[tuple[str, str, str]]:
    """(symbol, label, kind) for every group read against SPY."""
    out = [(s, LABELS.get(s, s), "sector")
           for s in settings.get("rankings.sector_etfs", []) or []]
    seen = {s for s, _, _ in out}
    for symbol, label in settings.get("rankings.radar_groups", []) or []:
        if symbol not in seen and symbol != "SPY":
            out.append((str(symbol), str(label), "group"))
            seen.add(symbol)
    return out


def symbols() -> list[str]:
    """Everything the radar needs loaded beside the universe."""
    out = [s for a, b, _ in pairs() for s in (a, b)] + [s for s, _, _ in groups()]
    return list(dict.fromkeys(out))


def _closes(bars: Sequence[Bar]) -> dict[dt.date, float]:
    return {b.date: b.close for b in bars if b.close and b.close > 0}


def readings(a: dict, b: dict, offsets: Sequence[int] = (0,)) -> dict[int, dict]:
    """{offset: reading} on the shared dates, offset sessions back from the last.

    A reading is rs per window (percent change of the ratio a/b over that many
    shared sessions) and the three trend flags. Missing where the history is
    too short, never zero.
    """
    dates = sorted(set(a) & set(b))
    ratio = [a[d] / b[d] for d in dates]
    n = len(ratio)
    csum = [0.0]
    for r in ratio:
        csum.append(csum[-1] + r)

    def ma(i: int, w: int) -> float | None:
        return (csum[i + 1] - csum[i + 1 - w]) / w if i + 1 >= w else None

    out: dict[int, dict] = {}
    for off in offsets:
        i = n - 1 - off
        if i < 21:
            continue
        row: dict = {"date": dates[i].isoformat()}
        for w in WINDOWS:
            row[f"rs{w}"] = (round((ratio[i] / ratio[i - w] - 1) * 100, 2)
                             if i >= w and ratio[i - w] else None)
        m21, m42, m63, m126 = ma(i, 21), ma(i, 42), ma(i, 63), ma(i, 126)
        row["t21_63"] = None if m21 is None or m63 is None else m21 > m63
        row["t42_126"] = None if m42 is None or m126 is None else m42 > m126
        row["t63_126"] = None if m63 is None or m126 is None else m63 > m126
        out[off] = row
    return out


def aligned(row: dict | None) -> str | None:
    """full / partial / none, or None when the flags cannot all be read."""
    if not row:
        return None
    flags = [row.get("t21_63"), row.get("t42_126"), row.get("t63_126")]
    if any(f is None for f in flags):
        return None
    k = sum(1 for f in flags if f)
    return "full" if k == 3 else "partial" if k else "none"


def spark(a: dict, b: dict, n: int = SPARK) -> list[float]:
    """The ratio's last n sessions, rebased to 100 at the first."""
    dates = sorted(set(a) & set(b))[-n:]
    if not dates:
        return []
    base = a[dates[0]] / b[dates[0]]
    return [round(100 * (a[d] / b[d]) / base, 2) for d in dates]


def _chg(now: dict, then: dict | None, key: str) -> float | None:
    if not then or now.get(key) is None or then.get(key) is None:
        return None
    return round(now[key] - then[key], 2)


def compute(market: Market) -> dict | None:
    """The radar payload, or None when SPY itself has no bars."""
    spy = _closes(market.series.get("SPY") or [])
    if len(spy) < 30:
        return None
    offsets = range(WEEK + 1)

    key_pairs = []
    for a, b, label in pairs():
        A, B = _closes(market.series.get(a) or []), _closes(market.series.get(b) or [])
        r = readings(A, B, offsets)
        if 0 not in r:
            continue
        now, start = r[0], r.get(WEEK)
        key_pairs.append({"a": a, "b": b, "label": label, "now": now, "start": start,
                          "path": [r[o]["rs126"] for o in reversed(offsets) if o in r],
                          "chg126": _chg(now, start, "rs126"),
                          "aligned": aligned(now), "spark": spark(A, B)})

    rows = []
    for symbol, label, kind in groups():
        A = _closes(market.series.get(symbol) or [])
        if len(A) < 30:
            continue
        r = readings(A, spy, offsets)
        if 0 not in r:
            continue
        now, start = r[0], r.get(WEEK)
        rows.append({"symbol": symbol, "label": label, "kind": kind,
                     "now": now, "start": start, "readings": r,
                     "aligned": aligned(now), "aligned_start": aligned(start),
                     "chg126": _chg(now, start, "rs126"),
                     "chg21": _chg(now, start, "rs21")})
    rows.sort(key=lambda g: -(g["now"]["rs126"] if g["now"]["rs126"] is not None else -999))

    breadth = []
    for off in reversed(offsets):
        at = [g["readings"][off] for g in rows if off in g["readings"]]
        if not at:
            continue
        states = [aligned(r) for r in at]
        breadth.append({
            "date": at[0]["date"], "n": len(at),
            **{f"pos{w}": sum(1 for r in at if (r.get(f"rs{w}") or 0) > 0)
               for w in (21, 42, 63, 126)},
            "full": states.count("full"), "partial": states.count("partial"),
            "none": states.count("none"),
        })

    has126 = [g for g in rows if g["now"]["rs126"] is not None]
    leaders = [g for g in has126 if g["aligned"] == "full" and g["now"]["rs126"] > 0
               and (g["now"]["rs21"] or 0) > 0 and (g["chg126"] or 0) >= 0]
    cooling = [g for g in has126 if g["now"]["rs126"] > 0 and g not in leaders
               and ((g["now"]["rs21"] or 0) < 0 or (g["chg126"] or 0) < 0)]
    improving = sorted([g for g in has126 if (g["chg126"] or 0) > 0 and g not in leaders],
                       key=lambda g: -(g["chg126"] or 0))
    weakest = sorted([g for g in has126 if g["now"]["rs126"] < 0],
                     key=lambda g: g["now"]["rs126"])
    fell = sorted([g for g in has126 if (g["chg126"] or 0) < 0], key=lambda g: g["chg126"])

    spy_dates = sorted(spy)
    spy_week = (round((spy[spy_dates[-1]] / spy[spy_dates[-1 - WEEK]] - 1) * 100, 2)
                if len(spy_dates) > WEEK else None)
    by_pair = {f"{p['a']}/{p['b']}": p for p in key_pairs}
    b_then, b_now = (breadth[0], breadth[-1]) if breadth else ({}, {})

    def ref(g: dict) -> str:
        return g["symbol"]

    for g in rows:
        del g["readings"]
    return {
        "as_of": market.as_of.isoformat(),
        "from": b_then.get("date"), "to": b_now.get("date"),
        "windows": list(WINDOWS),
        "pairs": key_pairs,
        "groups": rows,
        "breadth": breadth,
        "map": {"leaders": [ref(g) for g in leaders[:6]],
                "cooling": [ref(g) for g in cooling[:6]],
                "improving": [ref(g) for g in improving[:4]],
                "weakest": [ref(g) for g in weakest[:4]],
                "fell": [ref(g) for g in fell[:4]]},
        "spy_week": spy_week,
        "read": classify(by_pair, b_then, b_now, spy_week),
        "watch": watch(by_pair, b_now, rows),
    }


def classify(P: dict, b0: dict, b1: dict, spy_week: float | None) -> dict:
    """One of five fixed labels for the week, with the readings behind it."""
    def v(key: str, w: int, which: str = "now") -> float | None:
        p = P.get(key)
        return None if not p or not p.get(which) else p[which].get(f"rs{w}")

    n = b1.get("n") or 1
    full_share = (b1.get("full") or 0) / n
    pos126_share = (b1.get("pos126") or 0) / n
    qqq, rsp = v("QQQ/SPY", 126), v("RSP/SPY", 126)
    iwq, iws = v("IWM/QQQ", 126), v("IWM/SPY", 126)

    reasons = []
    if qqq is not None:
        then = v("QQQ/SPY", 126, "start")
        moved = None if then is None else qqq - then
        verb = ("held" if moved is None or abs(moved) <= 0.05
                else "gained" if moved > 0 else "lost")
        reasons.append(f"Growth {verb} six-month strength against the market "
                       f"({qqq:+.2f}%" + ("" if moved is None else f", {moved:+.2f} on the week")
                       + ")")
    if iwq is not None:
        then = v("IWM/QQQ", 126, "start")
        crossed = then is not None and then <= 0 < iwq
        reasons.append(f"Small caps against growth {iwq:+.2f}% over six months"
                       + (", crossed positive this week" if crossed else ""))
    if iws is not None:
        reasons.append(f"Small caps against the market {iws:+.2f}%")
    if rsp is not None:
        reasons.append(f"Equal weight against the market {rsp:+.2f}%")
    if b1:
        line = (f"{b1.get('full', 0)} of {n} groups fully aligned ({full_share:.0%}), "
                f"{b1.get('pos126', 0)} positive over six months")
        if b0 and b0.get("full") != b1.get("full"):
            line += f"; fully aligned {b0.get('full')} → {b1.get('full')} on the week"
        reasons.append(line)
    if spy_week is not None:
        reasons.append(f"S&P 500 {spy_week:+.1f}% over the five sessions")

    falling = bool(b0 and b1 and b1.get("pos21", 0) < b0.get("pos21", 0)
                   and b1.get("pos63", 0) <= b0.get("pos63", 0))
    if rsp is not None and rsp >= 0 and full_share >= 0.4 and pos126_share >= 0.5:
        label, sub = ("Broad advance", "Most groups aligned and positive over six "
                      "months, with equal weight holding its edge.")
    elif falling and (spy_week or 0) <= -2 and (v("RSP/SPY", 21) or 0) < 0:
        label, sub = ("Deterioration", "Participation fell across the windows while "
                      "the index fell and equal weight lost ground.")
    elif qqq is not None and qqq > 0 and full_share < 0.4:
        label, sub = ("Narrow growth leadership", "Growth leads the market while most "
                      "groups are not aligned.")
    elif (qqq is not None and qqq < 0 and ((iwq or 0) > 0 or (rsp or 0) > 0)
          and full_share < 0.4):
        label, sub = ("Selective rotation", "Growth weakens, small caps or equal weight "
                      "hold up better, and participation stays narrow.")
    else:
        label, sub = "Mixed", "No relationship dominates and alignment is partial."
    return {"label": label, "sub": sub, "reasons": reasons,
            "full_share": round(100 * full_share),
            "pos126_share": round(100 * pos126_share)}


def watch(P: dict, b1: dict, rows: list[dict]) -> list[dict]:
    """What would change the read: each a threshold beside its current value."""
    out: list[dict] = []

    def pair(key: str, w: int, text: str) -> None:
        p = P.get(key)
        cur = None if not p else p["now"].get(f"rs{w}")
        if cur is not None:
            out.append({"q": text, "now": f"{cur:+.2f}%", "met": cur > 0})

    pair("IWM/SPY", 126, "Small caps ahead of the market over six months")
    pair("IWM/QQQ", 126, "Small caps ahead of growth over six months")
    pair("RSP/SPY", 126, "Equal weight ahead of the market over six months")
    pair("QQQ/SPY", 21, "Growth ahead of the market over the last month")
    if b1:
        n = b1.get("n", 0)
        out.append({"q": "Fully aligned groups at 40% or more",
                    "now": f"{b1.get('full', 0)} of {n}",
                    "met": n > 0 and b1.get("full", 0) / n >= 0.4})
        out.append({"q": "Half the groups positive over six months",
                    "now": f"{b1.get('pos126', 0)} of {n}",
                    "met": n > 0 and b1.get("pos126", 0) / n >= 0.5})
    semis = next((g for g in rows if g["symbol"] in ("SMH", "SOXX")), None)
    if semis and semis["now"].get("rs21") is not None:
        out.append({"q": f"Semiconductors ahead of the market over the last month "
                         f"({semis['symbol']})",
                    "now": f"{semis['now']['rs21']:+.2f}%",
                    "met": semis["now"]["rs21"] > 0})
    return out


def digest_lines(payload: dict | None) -> dict | None:
    """The radar in the shape the weekly email reads."""
    if not payload:
        return None
    by = {g["symbol"]: g for g in payload["groups"]}

    def named(keys: list[str]) -> list[dict]:
        return [{"symbol": k, "label": by[k]["label"], "rs126": by[k]["now"]["rs126"],
                 "rs21": by[k]["now"]["rs21"]} for k in keys if k in by]

    return {"read": payload["read"],
            "pairs": [{"label": p["label"], "a": p["a"], "b": p["b"],
                       "rs126": p["now"]["rs126"],
                       "start126": (p["start"] or {}).get("rs126")}
                      for p in payload["pairs"]],
            "leaders": named(payload["map"]["leaders"][:4]),
            "weakest": named(payload["map"]["weakest"][:3]),
            "breadth": payload["breadth"][-1] if payload["breadth"] else None}
