"""The nightly briefing: one post's worth of the session, for X.

Composed from files the nightly already writes, and nothing else. There is no
analysis in here that the site does not already publish, so the post and the
site cannot say different things about the same session — which is the fault
this project keeps finding in other places, and would be worst of all in the
one piece of it that goes out under somebody's name.

It is delivered as a draft, not posted. A person reads it and posts it.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable

# ------------------------------------------------------------ the market read
#
# A port of web/lib/marketRead.ts, line for line, because the verdict at the
# top of this post and the verdict at the top of the home page are the same
# claim and must never disagree. The two are checked against each other on the
# same inputs rather than trusted to stay in step.

BLESS_AT = 3
WARN_AT = 2


def _card(cards: list[dict], key: str) -> dict | None:
    return next((c for c in cards if c.get("key") == key), None)


def read_market(cards: list[dict] | None, regime: dict | None) -> dict:
    """The home page's verdict, computed the same way."""
    cards = cards or []
    tests: list[dict] = []

    # An unknown regime is skipped, never scored as a negative.
    if regime and regime.get("above") is not None:
        tests.append({"label": f"{regime['symbol']} against its 200-day line",
                      "detail": regime.get("note", ""),
                      "score": 1 if regime["above"] else -1})

    breakouts, failed = _card(cards, "breakouts"), _card(cards, "failed_pokes")
    # Nothing cleared and nothing failed is a holiday or a gap, not a hostile
    # tape. 0 >= 0 * 1.5 is true, so it is caught before the comparison.
    if breakouts and failed and (breakouts["value"] > 0 or failed["value"] > 0):
        b, f = breakouts["value"], failed["value"]
        score = -1 if f >= b * 1.5 else 1 if b >= f else 0
        tests.append({"label": "Breakouts against failed pokes",
                      "detail": f"{b:.0f} cleared a pivot, {f:.0f} tested one "
                                "and fell back.",
                      "score": score})

    above50 = _card(cards, "above_50ma")
    if above50:
        v = above50["value"]
        tests.append({"label": "Above the 50-day line",
                      "detail": f"{v:.0f}% of the universe.",
                      "score": 1 if v >= 55 else -1 if v <= 40 else 0})

    uptrend = _card(cards, "confirmed_uptrend")
    if uptrend:
        v = uptrend["value"]
        tests.append({"label": "In a confirmed uptrend",
                      "detail": f"{v:.0f}% of the universe.",
                      "score": 1 if v >= 40 else -1 if v <= 25 else 0})

    measured = len(tests)
    if measured < 2:
        return {"verdict": "unknown",
                "headline": "Not enough breadth data to call it",
                "blurb": "", "tests": tests, "measured": measured}

    total = sum(t["score"] for t in tests)
    below_trend = bool(regime) and regime.get("above") is False
    if total >= BLESS_AT and not below_trend:
        return {"verdict": "in_gear", "headline": "The tape is in gear",
                "blurb": "Breakouts are being paid for and most of the market "
                         "is participating. This is the backdrop these screens "
                         "are built for.",
                "tests": tests, "measured": measured}
    if total <= -WARN_AT:
        return {"verdict": "against",
                "headline": "The tape is against breakouts",
                "blurb": "More names are failing at their pivots than holding "
                         "above them, and participation is thin. Bases that "
                         "look clean still tend to fail in this.",
                "tests": tests, "measured": measured}
    if below_trend and total >= 2:
        symbol = (regime or {}).get("symbol", "the benchmark")
        return {"verdict": "mixed",
                "headline": "Mixed, under a falling benchmark",
                "blurb": f"Breadth is holding up, but {symbol} is below its "
                         "200-day line. Breadth can look healthy for a week "
                         "inside a downtrend, and those are the weeks that cost "
                         "the most, because everything else is telling you to "
                         "buy.",
                "tests": tests, "measured": measured}
    return {"verdict": "mixed", "headline": "Mixed",
            "blurb": "Some of the market is working and some of it is not. "
                     "Breakouts go both ways in this, so the individual setup "
                     "matters more than usual.",
            "tests": tests, "measured": measured}


# ------------------------------------------------------------ the post

# The setting-up list: long bases just under their pivot. Relative strength has
# a floor because it is the one thing this site's own out-of-sample work found
# an edge in; the shape alone did not earn one, and a list sorted by shape would
# be recommending the part that does not work.
SETUP_MAX_BELOW_PCT = 5.0
SETUP_MIN_RS = 80
NAMES = 5


def _setting_up(setups: Iterable[dict], exclude: set[str]) -> list[dict]:
    """Long bases just under their pivot, one row per company, nearest first.

    Long only. The bearish screens read downward — their "pivot" is support and
    the break is below it — so a rising wedge 30% above its level is exactly
    where it should be, and listing it beside a VCP one point under its pivot
    would put two opposite readings under one heading.
    """
    best: dict[str, dict] = {}
    for setup in setups:
        if setup.get("stage") != "forming" or setup.get("direction") != "long":
            continue
        # A name that just broke out of one base and is forming another is
        # true and reads as a contradiction. It is named once, as the
        # breakout, which is the thing that happened.
        if setup["symbol"] in exclude:
            continue
        gap, rs = setup.get("now_vs_pivot_pct"), setup.get("rs_rating")
        if gap is None or not isinstance(rs, (int, float)):
            continue
        if not (-SETUP_MAX_BELOW_PCT <= gap <= 0) or rs < SETUP_MIN_RS:
            continue
        held = best.get(setup["symbol"])
        if held is None or gap > held["now_vs_pivot_pct"]:
            best[setup["symbol"]] = setup
    # Nearest first. now_vs_pivot_pct is negative below the pivot, so the
    # nearest is the largest value. The first draft of this line negated it
    # twice, the negations cancelled, and the list came out furthest-first
    # under a heading promising the opposite.
    return sorted(best.values(),
                  key=lambda s: (-s["now_vs_pivot_pct"], -s["rs_rating"]))


def _long_forming(setups: Iterable[dict]) -> dict[str, int]:
    """Forming bases per screen, long screens only.

    A rising wedge or a descending triangle forming is a bearish pattern
    setting up to break down; counting it under "bases forming" would add the
    opposite reading to the total.
    """
    counts: dict[str, int] = {}
    for setup in setups:
        if setup.get("stage") == "forming" and setup.get("direction") == "long":
            counts[setup["screen"]] = counts.get(setup["screen"], 0) + 1
    return counts


def _tape_sentence(read: dict, regime: dict | None) -> str | None:
    """The benchmark and the breakout test, joined by what they actually say.

    "But" only when the two point different ways and "and" when they agree —
    derived from the scores, never written in. A fixed "but breakouts are
    failing" would be a true sentence on the day it was drafted and a false one
    the first night breakouts held.
    """
    tests = {t["label"]: t for t in read["tests"]}
    pokes = tests.get("Breakouts against failed pokes")
    if not regime or regime.get("above") is None:
        return pokes["detail"] if pokes else None

    side = "above" if regime["above"] else "below"
    vs = regime.get("vs_200_pct")
    lead = (f"{regime['symbol']} {abs(vs):.1f}% {side} its 200-day"
            if vs is not None else f"{regime['symbol']} {side} its 200-day")
    if not pokes:
        return lead + "."

    state = {1: "holding", 0: "mixed", -1: "failing"}[pokes["score"]]
    trend = 1 if regime["above"] else -1
    joiner = ("while" if pokes["score"] == 0
              else "and" if pokes["score"] == trend else "but")
    return f"{lead}, {joiner} breakouts are {state}: {pokes['detail']}"


def _tickers(symbols: Iterable[str]) -> str:
    return " ".join(f"${s}" for s in symbols)


def compose(*, meta: dict, indexes: dict, breadth: dict, feed: dict,
            setups: list[dict], site: str = "thetape.cc", **_: Any) -> str:
    """The post, as text. Every figure comes from an argument."""
    names = {s["key"]: s["name"] for s in meta.get("screens", [])}
    session = dt.date.fromisoformat(meta["as_of"])
    regime = indexes.get("regime")
    read = read_market(breadth.get("cards"), regime)

    blocks: list[str] = [f"The tape, {session.month}/{session.day} close"]

    sentence = _tape_sentence(read, regime)
    if sentence:
        blocks.append(sentence)

    counts = _long_forming(setups)
    if counts:
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:2]
        most = " and ".join(names.get(k, k) for k, _ in top)
        blocks.append(f"{sum(counts.values()):,} bases forming across "
                      f"{len(counts)} screens, most in {most}.")

    fresh = sorted(feed.get("setups") or [],
                   key=lambda r: -(r.get("rs_rating") or 0))[:NAMES]
    if fresh:
        blocks.append("Strongest fresh breakouts: "
                      + _tickers(r["symbol"] for r in fresh))

    near = _setting_up(setups, {r["symbol"] for r in fresh})[:NAMES]
    if near:
        blocks.append("Closest to a pivot: "
                      + _tickers(s["symbol"] for s in near))

    blocks.append(site)
    return "\n\n".join(blocks)
