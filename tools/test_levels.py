"""Offline checks on the price levels: the anchored VWAP, last week's range,
the reclaim rule and the index divergence sentence.

Run: python tools/test_levels.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from data.types import Bar  # noqa: E402
from patterns import avwap, detectors, levels, reclaim  # noqa: E402
from patterns.indicators import sma  # noqa: E402
from patterns.params import (FOLLOWTHROUGH_KEYS, LEVEL_SCREEN_KEYS, SCREENS,  # noqa: E402
                             SHAPE_SCREEN_KEYS, Params, funnel_steps)
from rankings import indexes  # noqa: E402

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:62} {got!r}")
    if not ok:
        failures.append(label)


def bar(day: dt.date, low: float, high: float, close: float, volume: float = 1000.0,
        open_: float | None = None) -> Bar:
    return Bar("TEST", day, close if open_ is None else open_, high, low, close, volume)


def sessions(start: dt.date, count: int, skip: set[dt.date] | None = None) -> list[dt.date]:
    """Weekdays from `start`, leaving out any in `skip`."""
    out, day = [], start
    while len(out) < count:
        if day.weekday() < 5 and day not in (skip or set()):
            out.append(day)
        day += dt.timedelta(days=1)
    return out


# ---- anchored VWAP: the arithmetic
print("anchored VWAP")
d = sessions(dt.date(2026, 3, 2), 4)
four = [bar(d[0], 9, 11, 10, 100),       # typical 10
        bar(d[1], 18, 22, 20, 300),      # typical 20
        bar(d[2], 28, 32, 30, 600),      # typical 30
        bar(d[3], 30, 30, 30, 0)]        # nothing traded: counts for nothing
check("typical price is the mean of high, low and close", avwap.typical(four[0]), 10.0)
check("weighted by volume from the anchor", avwap.value(four, 0), 25.0)
check("a later anchor leaves the earlier sessions out", avwap.value(four, 1),
      (20 * 300 + 30 * 600) / 900)
check("a session with no volume moves nothing", avwap.value(four, 0, 3), avwap.value(four, 0))
check("nothing traded at all is no figure, not zero", avwap.value(four, 3), None)
check("running totals up to a bar", avwap.totals(four, 0, 2), (10 * 100 + 20 * 300, 400.0))

rows = avwap.summary(four[:3], [("earnings", 0), ("breakout", None), ("year", 5)], shipped=2)
check("an anchor the stock lacks, or past the bars, has no row",
      [r["anchor"] for r in rows], ["earnings"])
row = rows[0]
check("the row carries the figure", row["value"], 25.0)
check("and its first session", row["from"], d[0].isoformat())
check("the close is above it", (row["above"], row["vs_pct"]), (True, 20.0))
check("the seed is everything before the first shipped bar",
      (row["seed_money"], row["seed_volume"]), (1000.0, 100.0))
# The browser's line: seed plus the shipped bars must land on the same figure.
money, volume = row["seed_money"], row["seed_volume"]
for b in four[1:3]:
    money += avwap.typical(b) * b.volume
    volume += b.volume
check("seed plus the shipped bars rebuilds the figure", money / volume, 25.0)
inside = avwap.summary(four[:3], [("earnings", 1)], shipped=3)[0]
check("an anchor inside the shipped bars needs no seed",
      (inside["seed_money"], inside["seed_volume"]), (0.0, 0.0))

# Crossing: yesterday under the line, today over it.
cross = [bar(d[0], 99, 101, 100, 100), bar(d[1], 89, 91, 90, 100), bar(d[2], 100, 112, 110, 100)]
check("closed back above it today", avwap.summary(cross, [("earnings", 0)], 3)[0]["crossed"], "up")
fall = [bar(d[0], 99, 101, 100, 100), bar(d[1], 109, 111, 110, 100), bar(d[2], 88, 100, 90, 100)]
check("closed back below it today", avwap.summary(fall, [("earnings", 0)], 3)[0]["crossed"], "down")
check("no change of side is no crossing",
      avwap.summary(four[:3], [("earnings", 0)], 3)[0]["crossed"], None)

# Which session carried the report.
e = sessions(dt.date(2026, 5, 4), 6)                       # Mon 4 May .. Mon 11 May
quiet = [bar(day, 9, 11, 10, 100) for day in e]
check("a report on a session, with no heavier one after, is that session",
      avwap.earnings_session(quiet, e[2]), 2)
after_close = list(quiet)
after_close[3] = bar(e[3], 9, 13, 12, 900)
check("a heavier session after it is the news day (reported after the close)",
      avwap.earnings_session(after_close, e[2]), 3)
check("a report dated on a Saturday lands on Monday",
      avwap.earnings_session(quiet, dt.date(2026, 5, 9)), 5)
check("a report after the last bar has no session",
      avwap.earnings_session(quiet, dt.date(2026, 6, 1)), None)

y = sessions(dt.date(2025, 12, 29), 6)                     # three in 2025, three in 2026
year_bars = [bar(day, 9, 11, 10) for day in y]
check("the year's first session", avwap.year_session(year_bars), 3)
check("a history that starts inside the year has no year anchor",
      avwap.year_session(year_bars[3:]), None)

# ---- calendar weeks, across a holiday
print("\nlast week's range")
# Thanksgiving 2026: Thursday 26 November is no session. The week of the 23rd
# has four; the week before has five.
thanks = sessions(dt.date(2026, 11, 16), 12, skip={dt.date(2026, 11, 26)})
tb = [bar(day, 100 - i, 110 + i, 105) for i, day in enumerate(thanks)]
spans = reclaim.weeks(tb)
check("three calendar weeks", [m.isoformat() for m, _, _ in spans],
      ["2026-11-16", "2026-11-23", "2026-11-30"])
check("the holiday week has four sessions", spans[1][2] - spans[1][1] + 1, 4)
check("a Friday belongs to its own Monday", reclaim.week_of(dt.date(2026, 11, 27)),
      dt.date(2026, 11, 23))
prior = reclaim.prior_week(tb)
check("seen from 2 December, last week is the holiday week", prior["week_of"], "2026-11-23")
check("its four sessions", prior["sessions"], 4)
check("its low is the lowest low of those four", prior["low"], 100 - 8)
check("its high the highest high", prior["high"], 110 + 8)
check("one week of history has no last week", reclaim.prior_week(tb[:5]), None)
check("no bars, no last week", reclaim.prior_week([]), None)
# A Monday holiday: the week starts on the Tuesday and is still that week.
mon = sessions(dt.date(2026, 8, 31), 9, skip={dt.date(2026, 9, 7)})    # Labor Day
mb = [bar(day, 50, 60, 55) for day in mon]
check("a week that opens on a Tuesday is keyed to its Monday",
      [m.isoformat() for m, _, _ in reclaim.weeks(mb)], ["2026-08-31", "2026-09-07"])

summary = levels.summary(tb)
check("the levels block carries last week", summary["prior_week"]["week_of"], "2026-11-23")
check("and a normal day as a percent of the close",
      summary["atr_pct"], round(100.0 * summary["atr"] / summary["close"], 2))
quiet_day = [bar(day, 99, 101, 100) for day in sessions(dt.date(2026, 1, 5), 30)]
check("a stock that ranges 2 on a 100 close moves about 2% a day",
      levels.summary(quiet_day)["atr_pct"], 2.0)

# ---- the reclaim rule's edges
print("\nthe reclaim rule")
week1 = sessions(dt.date(2026, 6, 1), 5)
week2 = sessions(dt.date(2026, 6, 8), 5)
week3 = sessions(dt.date(2026, 6, 15), 5)


def chart(second: list[tuple[float, float, float]],
          third: list[tuple[float, float, float]] | None = None) -> list[Bar]:
    """Week one holds a low of 100; the later weeks are (low, high, close)."""
    out = [bar(day, 100, 106, 104) for day in week1]
    out += [bar(day, *row) for day, row in zip(week2, second)]
    out += [bar(day, *row) for day, row in zip(week3, third or [])]
    return out


steady = (101.0, 106.0, 104.0)
same = reclaim.events(chart([steady, (99.0, 105.0, 103.0), steady, steady, steady]))
check("under the low and back above by the close is one event", len(same), 1)
ev = same[0]
check("the level is last week's low", ev.level, 100.0)
check("reclaimed on the session it broke", (ev.undercut_idx, ev.reclaim_idx), (6, 6))
check("how far under, as a percent of the level", round(ev.undercut_pct, 2), 1.0)

check("a low exactly on the level is not under it",
      reclaim.events(chart([steady, (100.0, 105.0, 103.0), steady, steady, steady])), [])
on_it = reclaim.events(chart([steady, (99.0, 105.0, 100.0), (99.5, 104.0, 103.0),
                              steady, steady]))
check("a close exactly on the level is not back above it", on_it[0].reclaim_idx, 7)
late = chart([steady, (99.0, 103.0, 99.5), (98.5, 100.5, 99.8), (99.0, 104.0, 103.0), steady])
check("back above on the third session is too late at one session's grace",
      reclaim.events(late, max_reclaim_sessions=1), [])
check("and in time at two", reclaim.events(late, max_reclaim_sessions=2)[0].reclaim_idx, 8)
check("the low reported is the deepest of the trip",
      reclaim.events(late, max_reclaim_sessions=2)[0].low, 98.5)
deep = chart([steady, (95.0, 105.0, 103.0), steady, steady, steady])
check("5% under is a breakdown at a 4% limit", reclaim.events(deep, max_undercut_pct=4.0), [])
check("and an event at 6%", len(reclaim.events(deep, max_undercut_pct=6.0)), 1)
exact = chart([steady, (96.0, 105.0, 103.0), steady, steady, steady])
check("exactly 4% under passes a 4% limit", len(reclaim.events(exact, max_undercut_pct=4.0)), 1)

# The live edge: still under it, and whether there is time left.
check("under it today with a session left is kept, unreclaimed",
      [e.reclaim_idx for e in reclaim.events(chart([steady, (99.0, 103.0, 99.5)]))], [None])
check("still under it when the grace has run out is dropped",
      reclaim.events(chart([steady, (99.0, 103.0, 99.5), (98.8, 100.0, 99.0),
                            (98.9, 100.0, 99.2)])), [])
# Friday's undercut, Monday's reclaim: the level stays the one that was broken.
across = chart([steady, steady, steady, steady, (99.0, 103.0, 99.5)],
               [(99.2, 104.0, 103.0), steady, steady, steady, steady])
found = reclaim.events(across)
check("a Friday undercut reclaimed on Monday keeps the level that was broken",
      (found[0].level, found[0].reclaim_idx), (100.0, 10))
check("one event a week: a second dip under the same low is not a second event",
      len(reclaim.events(chart([(99.0, 105.0, 103.0), steady, (99.5, 105.0, 103.0),
                                steady, steady]))), 1)

# The health test is the session before, not the day.
closes = [b.close for b in same and chart([steady, (99.0, 105.0, 103.0), steady, steady, steady])]
flat50 = [103.0] * len(closes)
check("above its 50-day the session before", reclaim.healthy(ev, closes, flat50, [None] * 10), True)
check("under its 50-day the session before",
      reclaim.healthy(ev, closes, [105.0] * len(closes), [None] * 10), False)
check("50 under the 200 the session before",
      reclaim.healthy(ev, closes, flat50, [110.0] * len(closes)), False)
check("no 200-day yet is not held against it",
      reclaim.healthy(ev, closes, flat50, [None] * len(closes)), True)
check("no 50-day yet is", reclaim.healthy(ev, closes, [None] * len(closes), [None] * 10), False)

check("a close at the high is 100", reclaim.close_position(bar(d[0], 90, 100, 100)), 100.0)
check("a close at the low is 0", reclaim.close_position(bar(d[0], 90, 100, 90)), 0.0)
check("a session with no range is the middle", reclaim.close_position(bar(d[0], 9, 9, 9)), 50.0)
weak = chart([steady, (99.0, 109.0, 100.5), steady, steady, steady])
wc = [b.close for b in weak]
check("back above but closed near its low fails the close test",
      reclaim.screened(weak, wc, [103.0] * 10, [None] * 10, min_close_position=50.0), [])
check("and passes with the test off",
      len(reclaim.screened(weak, wc, [103.0] * 10, [None] * 10, min_close_position=0.0)), 1)
far = [bar(week1[0] - dt.timedelta(days=7), 100, 200, 150)] + \
    chart([steady, (99.0, 105.0, 103.0), steady, steady, steady])
fc = [b.close for b in far]
check("48% below its high fails a 15% limit",
      reclaim.screened(far, fc, [103.0] * 11, [None] * 11, max_from_high_pct=15.0), [])
check("and passes with no limit",
      len(reclaim.screened(far, fc, [103.0] * 11, [None] * 11, max_from_high_pct=None)), 1)

kept = chart([steady, (99.0, 105.0, 103.0), steady, steady, steady])
check("holding above the level since: not lost", reclaim.lost_level(ev, kept), None)
lost = chart([steady, (99.0, 105.0, 103.0), steady, (98.0, 102.0, 99.0), steady])
check("a later close under the level ends it", reclaim.lost_level(ev, lost), 8)
detail = reclaim.details(ev, kept)
check("the card's facts", (detail["week_of"], detail["level"], detail["low"],
                           detail["reclaim_date"], detail["sessions_to_reclaim"]),
      ("2026-06-01", 100.0, 99.0, week2[1].isoformat(), 0))

# ---- the screen, end to end, on a built chart
print("\nthe screen")
check("it is a screen", "reclaim" in SCREENS, True)
check("its record is measured", "reclaim" in FOLLOWTHROUGH_KEYS, True)
check("it is a level screen, not a shape", ("reclaim" in LEVEL_SCREEN_KEYS,
                                            "reclaim" in SHAPE_SCREEN_KEYS), (True, False))
check("it is read upward", detectors.direction_of("reclaim"), "long")
params = Params("reclaim")
check("shipped dials", (params.min_rs, params.max_undercut_pct, params.max_reclaim_sessions,
                        params.max_from_52w_high_pct, params.min_close_position_pct,
                        params.max_sessions_tracked),
      (80, 4.0, 1, 15.0, 50.0, 20))
check("every dial that narrows has a funnel step",
      [s["key"] for s in funnel_steps("reclaim")],
      ["universe", "min_rs", "require_above_50ma", "require_50_above_200",
       "max_from_52w_high_pct", "max_undercut_pct", "max_reclaim_sessions",
       "min_close_position_pct"])


def trending(tail: list[tuple[float, float, float]], rs=95) -> detectors.Series:
    """Sixty weeks rising a little each session, then `tail` as the last bars."""
    days = sessions(dt.date(2025, 1, 6), 300 + len(tail))
    out = []
    for i, day in enumerate(days[:300]):
        base = 50.0 + 0.2 * i
        out.append(bar(day, base - 0.5, base + 0.5, base + 0.3))
    out += [bar(day, *row) for day, row in zip(days[300:], tail)]
    return detectors.Series(symbol="TEST", bars=out, rs_rating=rs, name="Test Co")


# The 300 rising sessions end on a Friday (Monday start, 60 whole weeks), at
# about 109.8; that week's low is its Monday's, 108.7.
level = 50.0 + 0.2 * 295 - 0.5
fresh = detectors.detect_reclaim(trending([(level - 1.0, 111.0, 110.6)]), params)
check("a leader swept and back above: a fresh reclaim",
      (fresh.stage, fresh.pivot, fresh.reclaim["sessions_to_reclaim"]),
      ("fresh_breakout", round(level, 2), 0))
check("the pivot cautions are not carried over",
      [f for f in fresh.flags if f in ("squat", "failed_poke")], [])
under = detectors.detect_reclaim(trending([(level - 1.0, 110.0, level - 0.4)]), params)
check("still under it tonight: the first bucket", (under.stage, under.reclaim["reclaim_date"]),
      ("forming", None))
check("a laggard is not listed",
      detectors.detect_reclaim(trending([(level - 1.0, 111.0, 110.6)], rs=60), params), None)
gone = detectors.detect_reclaim(
    trending([(level - 1.0, 111.0, 110.6), (level - 2.0, 110.0, level - 0.5)]), params)
check("back under the level the next day: played out, and said why",
      (gone.stage, gone.exit_reason if hasattr(gone, "exit_reason") else None)[0], "played_out")
old_tail = [(level - 1.0, 111.0, 110.6)] + [(110.2 + 0.2 * i, 111.4 + 0.2 * i, 111.0 + 0.2 * i)
                                            for i in range(25)]
check("after twenty sessions it is no longer listed",
      detectors.detect_reclaim(trending(old_tail), params), None)
held = detectors.detect_reclaim(trending(old_tail[:12]), params)
check("eleven sessions on and holding: climbing", held.stage, "climbing")

# ---- index divergence
print("\nindex divergence")
up = [100.0 + i for i in range(30)]
down = [200.0 - i for i in range(30)]
middle = [100.0] * 10 + [110.0] * 10 + [105.0] * 10
check("all at a high together is agreement", indexes.divergence({"SPY": up, "QQQ": up}), None)
check("none at an extreme is agreement",
      indexes.divergence({"SPY": middle, "QQQ": middle, "IWM": middle}), None)
alone = indexes.divergence({"SPY": middle, "QQQ": middle, "IWM": down})
check("one at a low alone", alone["kinds"],
      [{"kind": "low", "alone": ["IWM"], "others": ["SPY", "QQQ"]}])
low_now = min(middle[-20:])
check("the sentence names them plainly, with how far the others are from theirs",
      alone["sentence"],
      "The Russell 2000 closed at a 20-session low. The S&P 500 and the Nasdaq 100 "
      f"did not: {100 * (105 / low_now - 1):.1f}% and {100 * (105 / low_now - 1):.1f}% "
      "above theirs.")
high = indexes.divergence({"SPY": middle, "QQQ": up})
check("one at a high alone, two indexes",
      high["sentence"],
      "The Nasdaq 100 closed at a 20-session high. The S&P 500 did not: "
      f"{100 * (1 - 105 / 110):.1f}% below its own.")
both = indexes.divergence({"SPY": down, "QQQ": up, "IWM": middle})
check("a low and a high on the same night are both said",
      [k["kind"] for k in both["kinds"]], ["low", "high"])
check("an unknown fund is called by its ticker",
      indexes.divergence({"XYZ": up, "SPY": middle})["sentence"].startswith("XYZ closed"), True)
check("too little history for the window says nothing",
      indexes.divergence({"SPY": up[:10], "QQQ": down[:10]}), None)
check("one index alone cannot disagree", indexes.divergence({"SPY": up}), None)
check("the window is a dial", indexes.divergence({"SPY": middle, "QQQ": up}, window=5)["window"], 5)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL LEVELS CHECKS PASS")
