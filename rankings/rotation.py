"""The rotation scatter: strength now against momentum versus a month ago."""
from __future__ import annotations

from data.market import Market
from rankings import groups
from rankings.rs import Bundle

QUADRANTS = ("powering_up", "turning_up", "cooling_off", "falling_back")
LABELS = {
    "powering_up": "Powering up",
    "turning_up": "Turning up",
    "cooling_off": "Cooling off",
    "falling_back": "Falling back",
}


def quadrant_for(x: float | None, y: float | None) -> str | None:
    if x is None or y is None:
        return None
    strong = x >= 50
    rising = y >= 0
    if strong and rising:
        return "powering_up"
    if not strong and rising:
        return "turning_up"
    if strong and not rising:
        return "cooling_off"
    return "falling_back"


def stock_points(market: Market, bundle: Bundle) -> list[dict]:
    points = []
    for symbol in market.universe:
        rs = bundle.now.get(symbol)
        if not isinstance(rs, int):
            continue
        delta = bundle.change(symbol, "m1")
        points.append({
            "id": symbol,
            "label": symbol,
            "name": market.refs[symbol].name if symbol in market.refs else symbol,
            "x": rs,
            "y": delta,
            "quadrant": quadrant_for(rs, delta),
            "size": market.caps.get(symbol, 0.0),
        })
    return points


def group_points(market: Market, bundle: Bundle, kind: str,
                 breakout_symbols=()) -> list[dict]:
    rows = groups.aggregate(market, bundle, kind, breakout_symbols)
    points = []
    for r in rows:
        delta = r.get("rs_change_m1")
        points.append({
            "id": r["slug"],
            "label": r["name"],
            "name": r["name"],
            "x": r["rs_rating"],
            "y": delta,
            "quadrant": quadrant_for(r["rs_rating"], delta),
            "size": r["market_value"],
            "members": r["members"],
            "leaders": r["leaders"],
            "fresh_breakouts": r["fresh_breakouts"],
        })
    return points


def counts(points: list[dict]) -> dict[str, int]:
    out = {q: 0 for q in QUADRANTS}
    for p in points:
        if p["quadrant"]:
            out[p["quadrant"]] += 1
    return out


def heating_cooling(rows: list[dict], span: str = "m1") -> dict:
    key = f"rs_change_{span}"
    ranked = [r for r in rows if r.get(key) is not None]
    ranked.sort(key=lambda r: -r[key])
    trim = lambda r: {"slug": r["slug"], "name": r["name"], "rs_rating": r["rs_rating"],
                      "avg_member_rs": r["avg_member_rs"], "delta": r[key],
                      "leaders": r["leaders"], "fresh_breakouts": r["fresh_breakouts"],
                      "members": r["members"]}
    return {"heating": [trim(r) for r in ranked[:12]],
            "cooling": [trim(r) for r in reversed(ranked[-12:])]}


def compute(market: Market, bundle: Bundle, breakout_symbols=()) -> dict:
    industries = group_points(market, bundle, "industry", breakout_symbols)
    themes = group_points(market, bundle, "theme", breakout_symbols)
    stocks = stock_points(market, bundle)
    return {
        "as_of": market.as_of.isoformat(),
        "lookback_label": "versus one month ago",
        "quadrant_labels": LABELS,
        "industries": {"points": industries, "counts": counts(industries)},
        "themes": {"points": themes, "counts": counts(themes)},
        "stocks": {"points": stocks, "counts": counts(stocks)},
    }
