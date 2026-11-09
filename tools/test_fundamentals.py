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

# ---- quarter by quarter, and the read of the latest one
from data import earnings_read as er  # noqa: E402

def inst(end: str, val: float) -> dict:
    return {"end": end, "val": val, "filed": "2026-08-01"}

def shares(start: str, end: str, val: float) -> dict:
    return {"start": start, "end": end, "val": val, "filed": "2026-08-01"}

ENDS = [r["end"] for r in REVENUE if r["end"] != "2025-09-27"] + ["2025-09-27"]
full = {"facts": {"us-gaap": {
    "Revenues": {"units": {"USD": REVENUE}},
    "GrossProfit": {"units": {"USD": [dict(r, val=r["val"] * 0.5) for r in REVENUE[:-1]]
                              + [dict(REVENUE[-1], val=56)]}},
    "NetIncomeLoss": {"units": {"USD": [dict(r, val=-10) for r in REVENUE[:-1]]
                                + [dict(REVENUE[-1], val=-4)]}},
    "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": CFO}},
    "ShareBasedCompensation": {"units": {"USD": [
        fact("2025-09-28", "2025-12-27", 5), fact("2025-09-28", "2026-03-28", 10),
        fact("2025-09-28", "2026-06-27", 23)]}},
    "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [
        shares("2025-03-30", "2025-06-28", 100), shares("2026-03-29", "2026-06-27", 108)]}},
    "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [
        inst("2026-03-28", 50), inst("2026-06-27", 60)]}},
    "LongTermDebtNoncurrent": {"units": {"USD": [
        inst("2026-03-28", 100), inst("2026-06-27", 120)]}},
    "RevenueRemainingPerformanceObligation": {"units": {"USD": [inst("2026-06-27", 880)]}},
}}}
qs = f.quarterly(full["facts"])
check("quarters kept, oldest first", [q["end"] for q in qs][-2:], ["2026-03-28", "2026-06-27"])
check("derived fiscal Q4 has no share count", next(q["shares"] for q in qs
                                                   if q["end"] == "2025-09-27"), None)
check("cash flow by quarter in the quarterly rows", [q["cfo"] for q in qs][-3:], [40, 30, 25])
check("stock pay differenced from year to date", qs[-1]["sbc"], 13)
check("debt and cash at the quarter end", (qs[-1]["debt"], qs[-1]["cash"]), (120, 60))
parsed = f.parse(full, today=D("2026-08-15"))
check("parse carries the quarters", len(parsed["quarters"]), 7)

r = er.read(qs)
g = r["glance"]
check("revenue on the quarter before", g["rev_qoq"], -9.1)
check("revenue on a year ago", g["rev_yoy"], 25.0)
check("gross margin move in points", g["gm_pp"], 6.0)
check("share count on a year ago", g["dilution"], 8.0)
kinds = {x["key"]: (x["tone"], x["text"]) for x in r["flags"]}
check("growth of 20% or more is good", kinds["growth"][0], 1)
check("a net loss narrower than the last", kinds["profit"],
      (-1, "Net loss $4, narrower than $10 last quarter"))
check("dilution of 5% or more", kinds["funding"],
      (-1, "Share count +8.0% in a year: dilution"))
check("net debt under twice revenue is neutral", kinds["balance"][0], 0)
notes = {x["key"] for x in r["forensic"]}
check("stock pay at half of cash flow is noted", "sbc" in notes, True)
check("debt up a tenth is noted", "debt" in notes, True)
check("backlog against twelve months' revenue",
      any("2.0× trailing revenue" in x["text"] for x in r["forensic"]), True)
check("final read", (r["verdict"]["growth"], r["verdict"]["proof"]), ("REAL", "PENDING"))
check("the takeaway follows the flags", r["takeaway"],
      "Growth with the cash to show for it: the quarter confirms the thesis.")
check("the test names the first weak flag", r["test"].startswith("The next test is operating profit"), True)
check("a report two years after the newest quarter gets no card",
      er.read(qs, "2028-08-01"), None)
check("a report a month after the quarter covers it", er.read(qs, "2026-07-30")["covers"], True)
check("one quarter is not enough to read", er.read(qs[:1]), None)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL FUNDAMENTALS CHECKS PASS")
