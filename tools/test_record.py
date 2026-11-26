"""Offline: the screens' record and its on-watch rule, and the research ledger.

    python tools/test_record.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from publish import ledger, record                 # noqa: E402

FAILED: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:<70} {got!r}"
          + ("" if ok else f"   want {want!r}"))
    if not ok:
        FAILED.append(label)


def breakout(pct20=None, bench20=1.0, pct5=None, close=100.0, pivot=99.0) -> dict:
    """A breakout as follow-through lists one. A horizon it has not reached
    is simply absent."""
    horizons = {}
    if pct5 is not None:
        horizons["5"] = {"pct": pct5, "bench_pct": 0.5}
    if pct20 is not None:
        horizons["20"] = {"pct": pct20, "bench_pct": bench20}
    return {"symbol": "X", "breakout_close": close, "pivot": pivot, "horizons": horizons}


def follow(**screens) -> dict:
    return {"as_of": "2026-11-25", "window_days": 180, "benchmark": "SPY",
            "horizons": [5, 20, 60],
            "screens": {key: {"screen": key, "name": key.upper(),
                              "total": len(rows), "settled": len(rows),
                              "failed_fast": 0, "share_failed_pct": 0.0,
                              "breakouts": rows} for key, rows in screens.items()}}


# ------------------------------------------------------------ a horizon
print("One screen at one horizon:")
rows = [breakout(4.0, 1.0), breakout(-2.0, 1.0), breakout(-0.5, None),
        breakout(pct5=3.0)]
at = record.horizon(rows, 20)
check("a breakout too young for the horizon is not counted", at["n"], 3)
check("how many were up, and the share", (at["up"], at["share_up_pct"]), (1, 33.3))
check("the mean and the median are both given", (at["mean_pct"], at["median_pct"]),
      (0.5, -0.5))
check("held is the close at the horizon against the pivot: -0.5% from 100 is above 99",
      (at["held"], at["share_held_pct"]), (2, 66.7))
check("the benchmark over the same sessions, where it is on file",
      (at["bench_mean_pct"], at["median_vs_bench_pct"]), (1.0, 0.0))
check("nothing reached it: no figures, not zeros",
      (record.horizon(rows, 60)["n"], record.horizon(rows, 60)["median_pct"]), (0, None))

# --------------------------------------------------------------- the rule
print("\nThe rule:")
weak = [breakout(-3.0, 1.0)] * 7 + [breakout(2.0, 1.0)] * 5        # 5 of 12 up, behind
falling = [breakout(-1.0, -6.0)] * 7 + [breakout(2.0, -6.0)] * 5   # 5 of 12 up, ahead
lagging = [breakout(1.0, 4.0)] * 12                                # all up, behind
strong = [breakout(5.0, 1.0)] * 12
short = [breakout(-9.0, 1.0)] * 11
made = record.build(
    follow(weak=weak, falling=falling, lagging=lagging, strong=strong, short=short),
    [("weak", "Weak"), ("falling", "Falling"), ("lagging", "Lagging"),
     ("strong", "Strong"), ("short", "Short"), ("shape", "A shape"), ("new", "New")],
    replayable={"weak", "falling", "lagging", "strong", "short", "new"})
by = record.by_screen(made)
check("fewer than half up AND behind the benchmark: on watch",
      by["weak"]["status"], "on_watch")
check("with the numbers that put it there",
      by["weak"]["reason"],
      "5 of 12 breakouts were up 20 sessions on (42%), and the typical one trailed "
      "SPY by 4.0 points.")
check("fewer than half up but ahead of a falling market: holding",
      by["falling"]["status"], "holding")
check("behind a roaring market while every breakout rose: holding",
      by["lagging"]["status"], "holding")
check("a good record: holding", by["strong"]["status"], "holding")
check("eleven breakouts, every one down: too few to judge, not a verdict",
      (by["short"]["status"], by["short"]["reason"]),
      ("too_few", "Eleven breakouts have run 20 sessions; twelve are needed before "
                  "there is a verdict."))
check("a screen whose past cannot be rebuilt has no record, and says why",
      (by["shape"]["status"], by["shape"]["measured"],
       by["shape"]["reason"].startswith("No breakouts on record.")),
      ("too_few", False, True))
check("a screen added tonight starts as too few to judge",
      (by["new"]["status"], by["new"]["reason"]),
      ("too_few", "No breakout has run 20 sessions; twelve are needed before there "
                  "is a verdict."))
check("every screen has its row, in the order given",
      [row["screen"] for row in made["screens"]],
      ["weak", "falling", "lagging", "strong", "short", "shape", "new"])
check("the count of each", made["counts"], {"holding": 3, "on_watch": 1, "too_few": 3})
check("the rule is published in words with its numbers",
      ("twelve breakouts" in made["rule"]["text"], "fewer than half" in made["rule"]["text"],
       made["rule"]["min_to_judge"], made["rule"]["judge_horizon"]), (True, True, 12, 20))

# The label comes off by the same rule: no memory.
better = record.build(follow(weak=weak + [breakout(6.0, 1.0)] * 3), [("weak", "Weak")])
check("three good breakouts later the same screen is holding again",
      record.by_screen(better)["weak"]["status"], "holding")
no_bench = record.build(follow(weak=[breakout(-3.0, None)] * 12), [("weak", "Weak")])
check("with no benchmark on file a screen cannot be put on watch",
      record.by_screen(no_bench)["weak"]["status"], "holding")
check("a night with no follow-through at all still publishes every screen",
      [r["status"] for r in record.build(None, [("a", "A")], replayable={"a"})["screens"]],
      ["too_few"])
# A screen follow-through rebuilds some other way is counted like any other.
other = record.build(follow(level=[breakout(4.0, 1.0)] * 14), [("level", "Level")],
                     replayable={"weak"})
check("a screen follow-through holds is counted, whatever it is built on",
      (record.by_screen(other)["level"]["measured"],
       record.by_screen(other)["level"]["status"]), (True, "holding"))
check("no name of any stock is in the record",
      "symbol" in str(made["screens"]), False)

# ------------------------------------------------------------ the ledger
print("\nThe ledger:")
real = ledger.load()
ids = [entry["id"] for entry in real["entries"]]
check("the file in the repository validates", len(ids) > 0, True)
check("every id is used once", len(ids), len(set(ids)))
check("every verdict is one of the five",
      {entry["verdict"] for entry in real["entries"]} <= set(ledger.VERDICTS), True)
check("newest first", [e["date"] for e in real["entries"]],
      sorted((e["date"] for e in real["entries"]), reverse=True))
check("every entry names where in the repository it is recorded",
      all(entry["source"] for entry in real["entries"]), True)
check("every open question says what it is waiting for",
      all(entry["waiting_for"] for entry in real["entries"] if entry["verdict"] == "open"),
      True)
check("the failures are kept: something was refuted, and something refused",
      (real["counts"]["refuted"] > 0, real["counts"]["refused"] > 0), (True, True))
root = pathlib.Path(__file__).resolve().parent.parent
named = {source.split(":")[0] for entry in real["entries"] for source in entry["source"]}
check("every source named is a file that exists",
      sorted(name for name in named if not (root / name).exists()), [])

GOOD = {"id": "R01", "date": "2026-11-26", "question": "q", "measured": "m",
        "result": "r", "verdict": "held", "source": "DECISIONS.md: x"}


def refused(entries) -> str:
    try:
        ledger.validate(entries)
    except ledger.LedgerError as exc:
        return str(exc)
    return "accepted"


check("a good entry is accepted", refused([GOOD]), "accepted")
check("an id used twice", refused([GOOD, dict(GOOD)]), "R01: used twice")
check("a verdict outside the set",
      refused([{**GOOD, "verdict": "promising"}])[:36],
      "R01: verdict 'promising' is not one ")
check("a date that is not a date", refused([{**GOOD, "date": "last week"}]),
      "R01: date 'last week' is not a date")
check("a missing result", refused([{**GOOD, "result": ""}]), "R01: no result")
check("an open question with nothing it waits for",
      refused([{**GOOD, "verdict": "open"}]),
      "R01: an open question says what it is waiting for")
check("an id that is not an id", refused([{**GOOD, "id": "study-1"}]),
      "study-1: an id is R and two or three digits")
check("an empty ledger", refused([]), "the ledger has no entries")

print()
if FAILED:
    print(f"{len(FAILED)} CHECK(S) FAILED: {FAILED}")
    sys.exit(1)
print("ALL RECORD AND LEDGER CHECKS PASS")
