"""Leadership layers: every stock read against its own industry, bucketed.

Ported from Market Desk's coordinator/funnel.py, which reads its universe
against a sector or theme ETF. Here the benchmark is the stock's own industry,
as an equal-weighted index of the industry's members, so every one of the
site's names has a group to be measured against, not only those an ETF covers.

For each stock, relative strength is the percent change of stock / industry
over 21, 63 and 126 sessions. The industry's own state is the radar reading of
its index against SPY: fully, partially or not aligned, and positive or not
over six months. Industries under rankings.min_group_members have no index;
their stocks read against SPY with no group, and can only be turning, caution
or unconfirmed, as Market Desk's ungrouped names can.

Layers, first rule that holds:
  front         ahead of its industry at 21, 63 and 126 sessions, in an
                industry fully aligned and positive against the S&P 500
  specific      ahead at all three in an industry that is not positive:
                strength the group does not share
  developing    ahead at 21 and 63 and not behind at 126, in an industry at
                least partly aligned
  weak_in_strong  industry fully aligned and positive, stock behind at 21
                and at 126
  turning       behind at 126 but ahead at 21 and 63
  caution       behind at all three, in an industry that is not positive
  unconfirmed   everything else

A layer describes where a stock sits. It is not a call on it, and it plays no
part in any screen or rating.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from data import classify, settings
from data.market import Market
from rankings import groups as groups_mod
from rankings import radar

WINDOWS = (21, 63, 126)
MIN_PRICE = 3.0
# One session's move above this is a bad bar or an unadjusted split, and in an
# equal-weighted index of ten names it would move the whole industry.
MAX_DAILY = 0.5
# Sessions of index history: the 126-day reading needs 126, its trend flags 126.
HISTORY = 300
DAYS = 6          # tonight and the five sessions before it, for the week's path
TOP = 12

ORDER = ["front", "specific", "developing", "weak_in_strong", "turning", "caution",
         "unconfirmed"]
LABELS = {"front": "Front line", "specific": "Stock-specific strength",
          "developing": "Developing", "weak_in_strong": "Strong industry, weak stock",
          "turning": "Turning", "caution": "Caution", "unconfirmed": "Unconfirmed"}


def industry_index(market: Market, members: Sequence[str],
                   dates: Sequence[dt.date]) -> dict[dt.date, float]:
    """An equal-weighted index of the members' daily returns over `dates`."""
    closes = [{b.date: b.close for b in market.series.get(m) or [] if b.close > 0}
              for m in members]
    level, out = 100.0, {}
    for prev, day in zip(dates, dates[1:]):
        moves = []
        for c in closes:
            a, b = c.get(prev), c.get(day)
            if a and b:
                r = b / a - 1
                if abs(r) <= MAX_DAILY:
                    moves.append(r)
        if not out:
            out[prev] = level
        if moves:
            level *= 1 + sum(moves) / len(moves)
        out[day] = level
    return out


def layer(rs: dict, group: dict | None) -> str:
    """The layer for one stock: rs = {21, 63, 126} in percent, group its state."""
    r21, r63, r126 = rs.get(21), rs.get(63), rs.get(126)
    if r21 is None or r63 is None:
        return "unconfirmed"

    def pos(v):
        return v is not None and v > 0

    def neg(v):
        return v is not None and v < 0

    g_full = bool(group and group["aligned"] == "full")
    g_part = bool(group and group["aligned"] in ("full", "partial"))
    g_pos = bool(group and group["pos126"])
    if pos(r21) and pos(r63) and pos(r126) and g_full and g_pos:
        return "front"
    if pos(r21) and pos(r63) and pos(r126) and group is not None and not g_pos:
        return "specific"
    if pos(r21) and pos(r63) and not neg(r126) and g_part:
        return "developing"
    if g_full and g_pos and neg(r21) and neg(r126):
        return "weak_in_strong"
    if neg(r126) and pos(r21) and pos(r63):
        return "turning"
    if neg(r21) and neg(r63) and neg(r126) and not g_pos:
        return "caution"
    return "unconfirmed"


def _rs(stock: dict, bench: dict, dates: Sequence[dt.date], i: int) -> dict[int, float | None]:
    out: dict[int, float | None] = {}
    for w in WINDOWS:
        if i - w < 0:
            out[w] = None
            continue
        d0, d1 = dates[i - w], dates[i]
        s0, s1, b0, b1 = stock.get(d0), stock.get(d1), bench.get(d0), bench.get(d1)
        out[w] = (round(((s1 / s0) / (b1 / b0) - 1) * 100, 2)
                  if s0 and s1 and b0 and b1 else None)
    return out


def compute(market: Market) -> dict:
    """{"stocks": {symbol: reading}, "summary": the market-wide payload}."""
    floor = int(settings.get("rankings.min_group_members", 10))
    dates = [d for d in market.calendar if d <= market.as_of][-HISTORY:]
    spy = {b.date: b.close for b in market.bench_bars() if b.close > 0}
    universe = set(market.universe)
    members = {slug: [m for m in syms if m in universe]
               for slug, syms in groups_mod.membership(market, "industry").items()}

    indexes: dict[str, dict] = {}
    states: dict[str, dict[int, dict]] = {}
    names: dict[str, str] = {}
    for slug, syms in members.items():
        if len(syms) < floor or slug == "unclassified":
            continue
        idx = industry_index(market, syms, dates)
        reads = radar.readings(idx, spy, range(DAYS))
        if 0 not in reads:
            continue
        indexes[slug] = idx
        states[slug] = {off: {"aligned": radar.aligned(r), "pos126": (r.get("rs126") or 0) > 0,
                              "rs126": r.get("rs126"), "rs21": r.get("rs21")}
                        for off, r in reads.items()}
        names[slug] = groups_mod.display_name("industry", slug, market)

    n_dates = len(dates)
    closes_of = {s: {b.date: b.close for b in market.series.get(s) or [] if b.close > 0}
                 for s in market.universe}
    stocks: dict[str, dict] = {}
    path: list[dict] = []
    for off in reversed(range(DAYS)):
        i = n_dates - 1 - off
        if i < 0:
            continue
        counts = {k: 0 for k in ORDER}
        for symbol in market.universe:
            closes = closes_of[symbol]
            px = closes.get(dates[i])
            if not px or px < MIN_PRICE:
                continue
            slug = classify.slugify(market.industries.get(symbol, "Unclassified"))
            bench = indexes.get(slug)
            group = states[slug].get(off) if bench is not None else None
            rs = _rs(closes, bench if bench is not None else spy, dates, i)
            key = layer(rs, group)
            counts[key] += 1
            if off == 0:
                stocks[symbol] = {
                    "layer": key, "label": LABELS[key],
                    "vs": names[slug] if bench is not None else "S&P 500",
                    "vs_slug": slug if bench is not None else None,
                    "rs21": rs[21], "rs63": rs[63], "rs126": rs[126],
                    "group": group,
                }
        path.append({"date": dates[i].isoformat(), "n": sum(counts.values()), **counts})

    return {"stocks": stocks, "summary": summary(market, stocks, states, names, path)}


def summary(market: Market, stocks: dict, states: dict, names: dict,
            path: list[dict]) -> dict:
    """The market page: counts and their week, names per layer, industries."""
    def key_for(layer_key: str):
        if layer_key in ("front", "specific", "developing", "weak_in_strong"):
            return lambda r: -(r["rs126"] if r["rs126"] is not None else -999)
        if layer_key == "turning":
            return lambda r: -(r["rs63"] if r["rs63"] is not None else -999)
        if layer_key == "caution":
            return lambda r: r["rs126"] if r["rs126"] is not None else 999
        return lambda r: r["symbol"]

    rows = [{"symbol": s, "name": market.refs[s].name if s in market.refs else s,
             "vs": r["vs"], "vs_slug": r["vs_slug"], "layer": r["layer"],
             "rs21": r["rs21"], "rs63": r["rs63"], "rs126": r["rs126"]}
            for s, r in stocks.items()]
    top = {k: sorted([r for r in rows if r["layer"] == k], key=key_for(k))[:TOP]
           for k in ORDER if k != "unconfirmed"}

    by_industry: dict[str, dict] = {}
    for r in rows:
        if not r["vs_slug"]:
            continue
        slot = by_industry.setdefault(r["vs_slug"], {
            "slug": r["vs_slug"], "name": names.get(r["vs_slug"], r["vs"]),
            "aligned": states[r["vs_slug"]][0]["aligned"],
            "rs126": states[r["vs_slug"]][0]["rs126"],
            "n": 0, **{k: 0 for k in ORDER}})
        slot["n"] += 1
        slot[r["layer"]] += 1
    industries = sorted(by_industry.values(),
                        key=lambda g: (-(g["front"] + g["developing"]), -g["n"]))
    week_ago = path[0] if len(path) > 1 else None
    return {
        "as_of": market.as_of.isoformat(),
        "order": ORDER, "labels": LABELS,
        "n": path[-1]["n"] if path else 0,
        "grouped": sum(1 for r in rows if r["vs_slug"]),
        "counts": path[-1] if path else None,
        "yesterday": path[-2] if len(path) > 1 else None,
        "week_ago": week_ago,
        "path": path,
        "top": top,
        "industries": industries[:20],
        "industries_aligned": {
            "full": sum(1 for s in states.values() if s[0]["aligned"] == "full"),
            "partial": sum(1 for s in states.values() if s[0]["aligned"] == "partial"),
            "none": sum(1 for s in states.values() if s[0]["aligned"] == "none"),
            "positive": sum(1 for s in states.values() if s[0]["pos126"]),
            "n": len(states)},
    }
