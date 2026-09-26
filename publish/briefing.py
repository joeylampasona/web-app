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

# The setting-up list: long bases within this far of their pivot, strongest
# first by distance. Relative strength has a floor because it is the one thing
# this site's own out-of-sample work found an edge in; the shape alone did not
# earn one, and a list sorted by shape would be recommending the part that
# does not work.
SETUP_MAX_BELOW_PCT = 5.0
SETUP_MIN_RS = 80
SETUP_LIMIT = 12
BREAKOUT_LIMIT = 8
GROUP_LIMIT = 3

MARK = {1: "+", 0: "~", -1: "−"}


def _signed(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{'+' if value >= 0 else '−'}{abs(value):.{digits}f}%"


def _money(value: float | None) -> str:
    return "n/a" if value is None else f"${value:,.2f}"


def _setting_up(setups: Iterable[dict], exclude: set[str]) -> list[dict]:
    """Long bases just under their pivot, one row per company.

    Long only. The bearish screens read downward — their "pivot" is support and
    the break is below it — so a rising wedge sitting 30% above its level is
    exactly where it should be, and listing it beside a VCP one point under its
    pivot would put two opposite readings under one heading.
    """
    best: dict[str, dict] = {}
    for setup in setups:
        if setup.get("stage") != "forming" or setup.get("direction") != "long":
            continue
        # A name that just broke out of one base and is forming another is
        # true and reads as a contradiction two sections apart — "broke out"
        # and "4% below its pivot" about the same ticker. It is listed once,
        # as the breakout, which is the thing that happened.
        if setup["symbol"] in exclude:
            continue
        gap, rs = setup.get("now_vs_pivot_pct"), setup.get("rs_rating")
        if gap is None or not isinstance(rs, (int, float)):
            continue
        if not (-SETUP_MAX_BELOW_PCT <= gap <= 0) or rs < SETUP_MIN_RS:
            continue
        # A name on two screens appears once, under whichever base is nearer.
        held = best.get(setup["symbol"])
        if held is None or gap > held["now_vs_pivot_pct"]:
            best[setup["symbol"]] = setup
    # Nearest first. now_vs_pivot_pct is negative below the pivot, so the
    # nearest is the largest value — sorted descending. The first draft of this
    # line negated it twice, the negations cancelled, and the list came out
    # furthest-first under a heading promising the opposite.
    return sorted(best.values(),
                  key=lambda s: (-s["now_vs_pivot_pct"], -s["rs_rating"]))


def compose(*, meta: dict, indexes: dict, breadth: dict, feed: dict,
            setups: list[dict], sectors: dict, site: str = "thetape.cc") -> str:
    """The post, as text. Every figure comes from an argument."""
    names = {s["key"]: s["name"] for s in meta.get("screens", [])}
    session = dt.date.fromisoformat(meta["as_of"])
    read = read_market(breadth.get("cards"), indexes.get("regime"))

    lines: list[str] = []
    add = lines.append

    add(f"The Tape · {session.strftime('%A, %b')} {session.day} close")
    add("")

    add(f"{read['headline'].upper()}")
    if read["blurb"]:
        add(read["blurb"])
    add("")
    for test in read["tests"]:
        # The regime's detail already names the symbol, so its label would say
        # it twice. The others need their label for the number to mean anything.
        text = (test["detail"] if test["label"].endswith("200-day line")
                else f"{test['label']}: {test['detail']}")
        add(f"{MARK[test['score']]} {text}")
    add("")

    rows = indexes.get("rows") or []
    if rows:
        add("  ·  ".join(f"${r['symbol']} {_money(r['close'])} "
                         f"({_signed(r.get('change_pct'), 2)})" for r in rows))
        add("")

    # ---- fresh breakouts, strongest first
    fresh = sorted(feed.get("setups") or [],
                   key=lambda r: -(r.get("rs_rating") or 0))[:BREAKOUT_LIMIT]
    if fresh:
        add("FRESH BREAKOUTS — cleared a pivot in the last five sessions")
        for row in fresh:
            day = (row.get("breakout_metrics") or {}).get("breakout_day_gain_pct")
            extra = f" · {_signed(day)} on the day" if day is not None else ""
            add(f"${row['symbol']}  {names.get(row['screen'], row['screen'])} · "
                f"RS {row.get('rs_rating')}{extra}")
        add("")

    # ---- forming, named
    near = _setting_up(setups, {row["symbol"] for row in fresh})[:SETUP_LIMIT]
    if near:
        add(f"SETTING UP — within {SETUP_MAX_BELOW_PCT:.0f}% of a pivot, "
            f"RS {SETUP_MIN_RS}+")
        for s in near:
            gap = abs(s["now_vs_pivot_pct"])
            where = "at its pivot" if gap < 0.05 else f"{gap:.1f}% below"
            add(f"${s['symbol']}  {names.get(s['screen'], s['screen'])} · "
                f"RS {s['rs_rating']} · {where} {_money(s.get('pivot'))}")
        add("")

    # ---- where the bases are
    #
    # Long screens only. A rising wedge or a descending triangle forming is a
    # bearish pattern setting up to break down, and counting it under "bases
    # forming" would add the opposite reading to the total.
    counts: dict[str, int] = {}
    for setup in setups:
        if setup.get("stage") == "forming" and setup.get("direction") == "long":
            counts[setup["screen"]] = counts.get(setup["screen"], 0) + 1
    forming = sorted(((names.get(k, k), n) for k, n in counts.items()),
                     key=lambda pair: -pair[1])
    if forming:
        total = sum(count for _, count in forming)
        add(f"BASES FORMING — {total:,} across {len(forming)} screens")
        add(" · ".join(f"{name} {count}" for name, count in forming))
        add("")

    # ---- leading groups
    groups = (sectors.get("strongest") or [])[:GROUP_LIMIT]
    if groups:
        add("LEADING GROUPS")
        for g in groups:
            add(f"{g['name']} · RS {g['rs_rating']} · "
                f"{g['leaders']} of {g['members']} are leaders")
        add("")

    add(f"Every screen, every chart: {site}")
    add("Screens describe a chart's structure, not a forecast. In our own "
        "testing the shapes carried no measurable edge on their own; relative "
        "strength did. Not investment advice.")
    return "\n".join(lines)
