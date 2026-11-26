"""What the reclaim screen's dials cost and buy, on whatever bars are here.

Run by the probe workflow against the nightly's database, and by hand against
the synthetic one. It reads and prints; nothing is written.

    python tools/probe_reclaim.py

For each setting it prints how many reclaims the history holds, what the
stock did 5 and 20 sessions after the close that took the level back, how
often it closed back under the level within 5 sessions, and how many names
the screen would list tonight. Beside them, the same forward figures for
every in-order session of the same stocks, which is what the screen has to
beat to be saying anything.
"""
from __future__ import annotations

import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from patterns import reclaim                         # noqa: E402
from patterns.indicators import sma                  # noqa: E402

BASE = dict(max_undercut_pct=4.0, max_reclaim_sessions=2, above_50=True,
            stacked=True, max_from_high_pct=15.0, min_close_position=50.0)

SWEEPS = (
    ("no trend test at all", dict(above_50=False, stacked=False,
                                  max_from_high_pct=None, min_close_position=0.0)),
    ("+ above the 50, 50 over the 200", dict(max_from_high_pct=None,
                                            min_close_position=0.0)),
    ("+ within 25% of the high", dict(max_from_high_pct=25.0, min_close_position=0.0)),
    ("+ within 15% of the high", dict(min_close_position=0.0)),
    ("+ within 10% of the high", dict(max_from_high_pct=10.0, min_close_position=0.0)),
    ("AS SHIPPED (15%, closed upper half)", dict()),
    ("closed in the top third instead", dict(min_close_position=66.0)),
    ("undercut at most 2%", dict(max_undercut_pct=2.0)),
    ("undercut at most 6%", dict(max_undercut_pct=6.0)),
    ("undercut at most 10%", dict(max_undercut_pct=10.0)),
    ("same session only", dict(max_reclaim_sessions=0)),
    ("within 1 more session", dict(max_reclaim_sessions=1)),
    ("within 4 more sessions", dict(max_reclaim_sessions=4)),
)


def _median(values) -> str:
    return f"{statistics.median(values):+6.2f}" if values else "   n/a"


def _wins(values) -> str:
    return f"{100.0 * sum(1 for v in values if v > 0) / len(values):3.0f}%" if values else " n/a"


def report(series: dict, ratings: dict | None = None, min_rs: int = 70,
           fresh: int = 5, tracked: int = 20) -> dict:
    """Print the sweep. Returns the shipped row's figures, for a test or a caller."""
    panels = {}
    for symbol, bars in series.items():
        if len(bars) < 220:
            continue
        closes = [b.close for b in bars]
        panels[symbol] = (bars, closes, sma(closes, 50), sma(closes, 200))
    years = sum(len(p[0]) for p in panels.values()) / 252.0
    print(f"   {len(panels):,} names with 220 sessions or more, "
          f"{years:,.0f} stock-years of bars")
    if not panels:
        return {}

    base5, base20 = [], []
    for bars, closes, m50, m200 in panels.values():
        for i in range(200, len(bars) - 20, 5):
            if m50[i] and m200[i] and closes[i] > m50[i] > m200[i]:
                base5.append(100.0 * (closes[i + 5] / closes[i] - 1.0))
                base20.append(100.0 * (closes[i + 20] / closes[i] - 1.0))
    print(f"   every in-order session (above the 50, 50 over the 200), sampled weekly:"
          f" {len(base20):,}")
    print(f"      5 sessions on  median {_median(base5)}%  up {_wins(base5)}"
          f"     20 on  median {_median(base20)}%  up {_wins(base20)}\n")

    print(f"   {'setting':38}{'events':>8}{'/name/yr':>9}  {'med 5':>7} {'up':>4}"
          f"  {'med 20':>7} {'up':>4}  {'back under':>10}  {'tonight':>22}")
    shipped: dict = {}
    for label, over in SWEEPS:
        kw = dict(BASE)
        kw.update(over)
        count = lost = 0
        r5, r20 = [], []
        under = new = held = failed = leaders = 0
        for symbol, (bars, closes, m50, m200) in panels.items():
            found = reclaim.screened(bars, closes, m50, m200, **kw)
            last = len(bars) - 1
            for event in found:
                idx = event.reclaim_idx
                if idx is None:
                    continue
                count += 1
                if idx + 5 <= last:
                    r5.append(100.0 * (closes[idx + 5] / closes[idx] - 1.0))
                    lost += any(closes[i] < event.level for i in range(idx + 1, idx + 6))
                if idx + 20 <= last:
                    r20.append(100.0 * (closes[idx + 20] / closes[idx] - 1.0))
            if not found:
                continue
            event = found[-1]
            rated = ratings is None or (isinstance(ratings.get(symbol), int)
                                        and ratings[symbol] >= min_rs)
            if event.reclaim_idx is None:
                under += rated
            elif last - event.reclaim_idx <= tracked:
                if reclaim.lost_level(event, bars) is not None:
                    failed += 1
                elif last - event.reclaim_idx <= fresh:
                    new += rated
                else:
                    held += rated
        settled = sum(1 for _ in r5)
        tonight = f"{under} under {new} new {held} held {failed} lost"
        print(f"   {label:38}{count:>8,}{count / years:>9.2f}  {_median(r5)}% {_wins(r5)}"
              f"  {_median(r20)}% {_wins(r20)}"
              f"  {100.0 * lost / settled if settled else 0:>9.0f}%  {tonight:>22}")
        if not over:
            shipped = {"events": count, "under": under, "new": new, "held": held,
                       "lost": failed, "median_5": statistics.median(r5) if r5 else None,
                       "median_20": statistics.median(r20) if r20 else None}
    print("\n   'tonight' is names the screen would list: still under the level,"
          " reclaimed in the\n   last 5 sessions, reclaimed 6 to 20 ago and"
          " holding, and closed back under since."
          + ("" if ratings is None else f" The first\n   three are RS {min_rs} or better;"
                                        " the last is not rated, as on the site."))
    return shipped


def main() -> int:
    from data import store
    from data.market import load
    from rankings import rs
    conn = store.open_db()
    market = load(conn)
    bundle = rs.Bundle(market)
    print(f"   as of {market.as_of}")
    report({s: market.series.get(s) or [] for s in market.universe}, bundle.now)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
