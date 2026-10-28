"""Offline checks on the trailing-twelve-month arithmetic in data/fundamentals.

Run: python tools/test_fundamentals.py

The traps it guards are the ones real filings set: the fiscal fourth quarter
exists only inside the annual figure, cash flow is filed year to date, and a
missing filing must leave a gap rather than a total over the wrong twelve
months.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from data import fundamentals as f  # noqa: E402

D = dt.date.fromisoformat


def fact(start: str, end: str, val: float, filed: str = "2026-08-01") -> dict:
    return {"start": start, "end": end, "val": val, "filed": filed}


def doc(**concepts) -> dict:
    return {"facts": {"us-gaap": {name: {"units": {"USD": rows}}
                                  for name, rows in concepts.items()}}}


# A September fiscal year, like Apple's: three 10-Q quarters and a 10-K.
REVENUE = [
    fact("2024-09-29", "2024-12-28", 100), fact("2024-12-29", "2025-03-29", 90),
    fact("2025-03-30", "2025-06-28", 80), fact("2024-09-29", "2025-09-27", 380),
    fact("2025-09-28", "2025-12-27", 120), fact("2025-12-28", "2026-03-28", 110),
    fact("2026-03-29", "2026-06-27", 100),
]
# Cash flow, year to date in each 10-Q, from the same fiscal-year start.
CFO = [
    fact("2024-09-29", "2024-12-28", 30), fact("2024-09-29", "2025-03-29", 55),
    fact("2024-09-29", "2025-06-28", 75), fact("2024-09-29", "2025-09-27", 100),
    fact("2025-09-28", "2025-12-27", 40), fact("2025-09-28", "2026-03-28", 70),
    fact("2025-09-28", "2026-06-27", 95),
]

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:56} {got!r}")
    if not ok:
        failures.append(label)


quarters = f._quarters(f._durations(doc(Revenues=REVENUE)["facts"], ["Revenues"]))
check("fiscal Q4 derived as the year less three quarters",
      [(str(e), v) for _, e, v in quarters if e == D("2025-09-27")], [("2025-09-27", 110)])
check("quarters run back to back", len(quarters), 7)

out = f.parse(doc(Revenues=REVENUE, NetCashProvidedByUsedInOperatingActivities=CFO),
              today=D("2026-08-15"))
check("TTM is the four latest quarters (110+120+110+100)", out["revenue_ttm"], 440)
check("growth: latest quarter on the same one a year earlier", out["revenue_growth"], 25.0)
check("period ends at the latest quarter", out["period_end"], "2026-06-27")
cfo_q = f._quarters(f._durations(
    doc(X=CFO)["facts"], ["X"]))
check("cash flow quarters from year-to-date differences",
      [v for _, _, v in cfo_q][-4:], [25, 40, 30, 25])
check("free cash flow uses the same twelve months", out["fcf_ttm"], 120)

gap = [r for r in REVENUE if r["end"] != "2025-12-27"]
check("a missing quarter leaves no total",
      f.parse(doc(Revenues=gap), today=D("2026-08-15")), None)
check("figures over eighteen months old are not current",
      f.parse(doc(Revenues=REVENUE), today=D("2028-06-01")), None)
restated = REVENUE + [fact("2026-03-29", "2026-06-27", 104, filed="2026-09-01")]
check("a later filing of the same period replaces the first",
      f.parse(doc(Revenues=restated), today=D("2026-10-01"))["revenue_ttm"], 444)
check("a company with nothing in US GAAP", f.parse({"facts": {"ifrs-full": {}}}), None)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL FUNDAMENTALS CHECKS PASS")
