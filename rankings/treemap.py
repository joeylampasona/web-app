"""Industry treemap: sized by market value, labelled with RS, coloured by change."""
from __future__ import annotations

from data.market import Market
from rankings import groups
from rankings.rs import Bundle


def compute(market: Market, bundle: Bundle, breakout_symbols=()) -> dict:
    rows = groups.aggregate(market, bundle, "industry", breakout_symbols)
    total = sum(r["market_value"] for r in rows) or 1
    tiles = []
    for r in rows:
        tiles.append({
            "slug": r["slug"],
            "name": r["name"],
            "market_value": r["market_value"],
            "weight": round(r["market_value"] / total, 6),
            "rs_rating": r["rs_rating"],
            "rs_change_w1": r["rs_change_w1"],
            "rs_change_m1": r["rs_change_m1"],
            "rs_change_m3": r["rs_change_m3"],
            "fresh_breakouts": r["fresh_breakouts"],
            "members": r["members"],
            "leaders": r["leaders"],
        })
    tiles.sort(key=lambda t: -t["market_value"])
    return {"as_of": market.as_of.isoformat(), "windows": ["w1", "m1", "m3"], "tiles": tiles}
