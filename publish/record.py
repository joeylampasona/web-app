"""One scoreboard for the screens, and what happens to one that stops working.

The follow-through page lists every breakout a screen showed and how it went.
That answers "what happened to this one". It does not answer "is this screen
still earning its place", and nothing happened when the answer was no. This
does both, from the follow-through the nightly already computes: it reads that
payload and counts. No breakout is found again and no return is measured a
second way, so the scoreboard cannot disagree with the list beside it.

THE RULE, which the page prints in these words and these numbers:

  * A screen is judged at twenty sessions after the breakout, over the same
    180 days the follow-through covers.
  * It takes twelve breakouts that have run their twenty sessions to judge
    one. Fewer than that is "too few to judge", which is not a verdict.
  * A judged screen goes ON WATCH when fewer than half of those breakouts
    were up at twenty sessions AND the typical one trailed the benchmark over
    the same sessions. Both, not either: a screen whose typical breakout beat
    the market in a falling one is doing its job, and so is one that lags a
    roaring market while most of its breakouts still rise.
  * Otherwise it is HOLDING.

On watch is a label and nothing else. The screen stays where it was, with
every name it had, and carries the numbers that put it there. The label comes
off by the same rule on the first night the numbers no longer meet it: there
is no memory and no appeal, only the trailing window.

WHAT THE BASELINE IS, AND IS NOT. Beside each horizon is the benchmark's move
over the same sessions as each breakout. That is the only baseline the
pipeline has. There is no control group of stocks that did not break out, so
nothing here says a breakout beat a similar stock that stayed in its base.

Screens not built on a base (flags, wedges, triangles, the squeeze) have no
breakouts on record: the replay that rebuilds a screen's past can rebuild a
base and nothing else yet. They are "too few to judge" with nothing counted,
and the page says why. A screen added tomorrow starts the same way, whatever
it is built on, until twelve of its breakouts have run their twenty sessions.
"""
from __future__ import annotations

import statistics

#: The horizon, in sessions, a screen is judged at.
JUDGE_HORIZON = 20

#: Breakouts that must have run JUDGE_HORIZON sessions before there is a verdict.
MIN_TO_JUDGE = 12

#: Below this share up at the horizon, with the typical breakout behind the
#: benchmark, a screen is on watch.
MIN_SHARE_UP_PCT = 50.0

HOLDING, ON_WATCH, TOO_FEW = "holding", "on_watch", "too_few"

LABELS = {HOLDING: "Holding", ON_WATCH: "On watch", TOO_FEW: "Too few to judge"}

_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight",
          "nine", "ten", "eleven", "twelve")


def _count(n: int) -> str:
    return _WORDS[n] if 0 <= n < len(_WORDS) else f"{n:,}"


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 2) if values else None


def horizon(breakouts: list[dict], sessions: int) -> dict:
    """One screen at one horizon, from its breakouts as follow-through lists
    them. A breakout too young for the horizon is not in the count.

    "Held" is the close at the horizon against the pivot the stock cleared.
    Follow-through keeps the breakout day's close, the pivot and the move to
    the horizon, and the close at the horizon is those multiplied out."""
    key = str(sessions)
    reached = [b for b in breakouts if key in (b.get("horizons") or {})]
    moves = [float(b["horizons"][key]["pct"]) for b in reached]
    bench = [float(b["horizons"][key]["bench_pct"]) for b in reached
             if b["horizons"][key].get("bench_pct") is not None]
    excess = [float(b["horizons"][key]["pct"]) - float(b["horizons"][key]["bench_pct"])
              for b in reached if b["horizons"][key].get("bench_pct") is not None]
    held = sum(1 for b in reached
               if float(b["breakout_close"]) * (1.0 + float(b["horizons"][key]["pct"]) / 100.0)
               >= float(b["pivot"]))
    up = sum(1 for move in moves if move > 0)
    n = len(reached)
    return {
        "n": n,
        "up": up,
        "share_up_pct": round(100.0 * up / n, 1) if n else None,
        "held": held,
        "share_held_pct": round(100.0 * held / n, 1) if n else None,
        "mean_pct": _mean(moves),
        "median_pct": _median(moves),
        "bench_mean_pct": _mean(bench),
        "bench_median_pct": _median(bench),
        "median_vs_bench_pct": _median(excess),
    }


def judge(at: dict, benchmark: str, measured: bool = True) -> tuple[str, str]:
    """(status, the sentence that says why) for one screen at JUDGE_HORIZON."""
    n = at.get("n") or 0
    if n < MIN_TO_JUDGE:
        if not measured:
            return TOO_FEW, (
                "No breakouts on record. The replay that rebuilds a screen's "
                "past breakouts can rebuild a base and nothing else yet, and "
                "this screen is not built on one.")
        ran = ("No breakout has" if n == 0 else
               f"{_count(n).capitalize()} breakout{' has' if n == 1 else 's have'}")
        return TOO_FEW, (f"{ran} run {JUDGE_HORIZON} sessions; "
                         f"{_count(MIN_TO_JUDGE)} are needed before there is a verdict.")
    share = at["share_up_pct"]
    behind = at.get("median_vs_bench_pct")
    counted = (f"{at['up']} of {n} breakouts were up {JUDGE_HORIZON} sessions on "
               f"({share:.0f}%)")
    if behind is None:
        return HOLDING, (f"{counted}. The benchmark's move over the same sessions "
                         f"is not on file, so the screen cannot be put on watch.")
    against = (f"the typical one {'trailed' if behind < 0 else 'beat'} {benchmark} "
               f"by {abs(behind):.1f} points")
    if share < MIN_SHARE_UP_PCT and behind < 0:
        return ON_WATCH, f"{counted}, and {against}."
    return HOLDING, f"{counted}, and {against}."


def build(follow: dict | None, screens: list[tuple[str, str]],
          replayable: set[str] | None = None) -> dict:
    """The scoreboard: one row a screen, in the order given.

    `screens` is every screen the site has, as (key, name). One that
    follow-through has nothing for still gets its row. `replayable` is the
    set whose past breakouts can be rebuilt; a screen outside it is said to
    have no record rather than a short one.
    """
    follow = follow or {}
    benchmark = str(follow.get("benchmark") or "the benchmark")
    horizons = [int(h) for h in (follow.get("horizons") or [])] or [JUDGE_HORIZON]
    if JUDGE_HORIZON not in horizons:
        horizons = sorted(set(horizons) | {JUDGE_HORIZON})
    measured_keys = set(replayable if replayable is not None
                        else (follow.get("screens") or {}))
    rows = []
    for key, name in screens:
        found = (follow.get("screens") or {}).get(key) or {}
        breakouts = found.get("breakouts") or []
        by_horizon = {str(h): horizon(breakouts, h) for h in horizons}
        measured = key in measured_keys
        status, reason = judge(by_horizon[str(JUDGE_HORIZON)], benchmark, measured)
        rows.append({
            "screen": key, "name": name,
            "status": status, "label": LABELS[status], "reason": reason,
            "measured": measured,
            "total": int(found.get("total") or 0),
            "settled": int(found.get("settled") or 0),
            "failed_fast": int(found.get("failed_fast") or 0),
            "share_failed_pct": found.get("share_failed_pct"),
            "horizons": by_horizon,
        })
    return {
        "as_of": follow.get("as_of"),
        "window_days": follow.get("window_days"),
        "benchmark": benchmark,
        "horizons": horizons,
        "rule": {
            "judge_horizon": JUDGE_HORIZON,
            "min_to_judge": MIN_TO_JUDGE,
            "min_share_up_pct": MIN_SHARE_UP_PCT,
            "text": (
                f"A screen is judged {JUDGE_HORIZON} sessions after each breakout, "
                f"over the last {follow.get('window_days') or 180} days. It takes "
                f"{_count(MIN_TO_JUDGE)} breakouts that have run their "
                f"{JUDGE_HORIZON} sessions to judge one. A judged screen is on "
                f"watch when fewer than half of them were up at {JUDGE_HORIZON} "
                f"sessions and the typical one trailed {benchmark} over the same "
                f"sessions. Both, not either. On watch is a label: the screen "
                f"stays, with every name it had, and the label comes off by the "
                f"same rule."),
        },
        "counts": {status: sum(1 for row in rows if row["status"] == status)
                   for status in (HOLDING, ON_WATCH, TOO_FEW)},
        "copy": {
            "baseline": (
                f"Beside each figure is {benchmark}'s move over the same sessions "
                f"as each breakout. That is the only baseline kept. There is no "
                f"control group of stocks that did not break out, so nothing here "
                f"says a breakout beat a similar stock that stayed in its base."),
            "survivorship": (
                "The price history carries no delisted companies, so the "
                "breakouts that failed hardest are the ones missing. These "
                "figures are flattered, and the rule is applied to them as they "
                "are."),
            "held": ("Held is the close at the horizon against the pivot the "
                     "stock cleared."),
        },
        "screens": rows,
    }


def by_screen(record: dict | None) -> dict[str, dict]:
    return {row["screen"]: row for row in (record or {}).get("screens") or []}
