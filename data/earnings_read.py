"""The latest quarter as filed: what changed, flagged by fixed rules.

Ported from Market Desk's coordinator/earnings_read.py, from the same source:
the quarters data/fundamentals.py keeps from each company's XBRL filings.

Three parts, each a rule with a threshold rather than a judgment:

- At a glance: revenue against the quarter before and a year before, the
  gross margin and its move in points, operating and net income, operating
  and free cash flow, the share count against a year ago, cash and debt, and
  how many quarters of cash a negative free cash flow leaves.
- Flags, one per kind, each with a tone: growth, margin, profit, cash,
  funding, balance.
- What is not obvious: lines the same filing supports, shown only when they
  cross a threshold (deferred revenue carrying cash flow, stock pay against
  cash flow, depreciation against revenue, heavy capital spending, debt up on
  the quarter, interest against operating income, contracted backlog of half
  a year's revenue or more).

Left out on purpose: Market Desk's one-sentence takeaway and its two-word
verdict. Every other number on this site is a measurement, and a verdict on
the quarter would be the one place it says what to think.
"""
from __future__ import annotations

import datetime as dt

GROWTH_GOOD, GROWTH_BAD = 20.0, -5.0        # YoY revenue, percent
MARGIN_MOVE = 1.0                            # gross margin, points QoQ
DILUTION = 5.0                               # share count YoY, percent
BUYBACK_SHRINK = -1.0                        # share count YoY, percent
BACKLOG_SHARE = 0.5                          # of twelve months' revenue
DEFERRED_SHARE = 0.25                        # of operating cash flow
SBC_SHARE = 0.5                              # of operating cash flow
DNA_SHARE = 0.10                             # of revenue
CAPEX_SHARE = 0.5                            # of revenue
DEBT_JUMP = 0.10                             # on the quarter
INTEREST_SHARE = 0.5                         # of operating income
SHOWN = 8                                    # quarters drawn as bars


def _pct(a, b) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return round((a / b - 1) * 100, 1) if b > 0 else None


def _margin(part, whole) -> float | None:
    return None if part is None or not whole else round(100 * part / whole, 1)


def _year_ago(quarters: list[dict], i: int) -> dict | None:
    end = dt.date.fromisoformat(quarters[i]["end"])
    for q in reversed(quarters[:i]):
        if abs((end - dt.date.fromisoformat(q["end"])).days - 364) <= 21:
            return q
    return None


def money(v: float) -> str:
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1e9:
        return f"{sign}${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.0f}M"
    if a >= 1e3:
        return f"{sign}${a / 1e3:.0f}K"
    return f"{sign}${a:.0f}"


def read(quarters: list[dict] | None) -> dict | None:
    """The read of the latest quarter, or None with fewer than two quarters."""
    if not quarters or len(quarters) < 2:
        return None
    q, prev = quarters[-1], quarters[-2]
    ago = _year_ago(quarters, len(quarters) - 1)
    rev = q.get("revenue")
    gm = _margin(q.get("gross_profit"), rev)
    gm_prev = _margin(prev.get("gross_profit"), prev.get("revenue"))
    # Share counts are three-month weighted averages, so a fiscal fourth
    # quarter worked out from the year has none: the latest quarter that does
    # stands in for it, when it is the quarter before.
    counted = [x for x in quarters if x.get("shares")]
    latest_count = counted[-1] if counted else None
    if latest_count and (dt.date.fromisoformat(q["end"])
                         - dt.date.fromisoformat(latest_count["end"])).days > 100:
        latest_count = None
    shares_ago = _year_ago(counted, len(counted) - 1) if latest_count else None
    fcf, cfo = q.get("fcf"), q.get("cfo")
    cash, debt = q.get("cash"), q.get("debt")
    glance = {
        "end": q["end"],
        "revenue": rev,
        "revenue_qoq": _pct(rev, prev.get("revenue")),
        "revenue_yoy": _pct(rev, (ago or {}).get("revenue")),
        "gross_margin": gm,
        "gross_margin_move": (None if gm is None or gm_prev is None
                              else round(gm - gm_prev, 1)),
        "op_income": q.get("op_income"),
        "net_income": q.get("net_income"),
        "cfo": cfo,
        "fcf": fcf,
        "shares_yoy": _pct((latest_count or {}).get("shares"),
                           (shares_ago or {}).get("shares")),
        "cash": cash,
        "debt": debt,
        "runway_quarters": (round(cash / -fcf, 1)
                            if fcf is not None and fcf < 0 and cash else None),
    }

    flags: list[dict] = []

    def flag(kind: str, tone: str, text: str) -> None:
        flags.append({"kind": kind, "tone": tone, "text": text})

    yoy = glance["revenue_yoy"]
    if yoy is not None:
        if yoy >= GROWTH_GOOD:
            flag("growth", "good", f"Revenue {yoy:+.0f}% on a year ago")
        elif yoy <= GROWTH_BAD:
            flag("growth", "bad", f"Revenue {yoy:+.0f}% on a year ago")
        else:
            flag("growth", "neutral", f"Revenue {yoy:+.0f}% on a year ago")
    move = glance["gross_margin_move"]
    if move is not None and abs(move) >= MARGIN_MOVE:
        flag("margin", "good" if move > 0 else "bad",
             f"Gross margin {'up' if move > 0 else 'down'} {abs(move):.1f} points "
             f"on the quarter, to {gm:.1f}%")
    ni, ni_prev = q.get("net_income"), prev.get("net_income")
    if ni is not None:
        if ni >= 0:
            flag("profit", "good", "Profitable" if (ni_prev or 0) >= 0
                 else "Profitable, from a loss the quarter before")
        elif ni_prev is not None and ni_prev < 0:
            narrowed = ni > ni_prev
            flag("profit", "neutral" if narrowed else "bad",
                 f"Loss {'narrowed' if narrowed else 'widened'} to {money(ni)}")
        else:
            flag("profit", "bad", f"Loss of {money(ni)}")
    if fcf is not None:
        prev_fcf = prev.get("fcf")
        trend = ("" if prev_fcf is None
                 else ", better than the quarter before" if fcf > prev_fcf
                 else ", worse than the quarter before")
        if fcf >= 0:
            flag("cash", "good", f"Generating cash ({money(fcf)} free cash flow{trend})")
        else:
            runway = glance["runway_quarters"]
            flag("cash", "bad", f"Burning cash ({money(fcf)} free cash flow{trend}"
                 + (f"; {runway:.1f} quarters of cash at this rate" if runway else "")
                 + ")")
    capex = abs(q.get("capex") or 0.0)
    if cfo is not None and capex and capex > cfo:
        flag("funding", "bad", "Capital spending above operating cash flow")
    sh = glance["shares_yoy"]
    if sh is not None and sh >= DILUTION:
        flag("funding", "bad", f"Share count {sh:+.1f}% on a year ago")
    elif (sh is not None and sh <= BUYBACK_SHRINK) or (q.get("buyback") or 0) > 0:
        flag("funding", "good", "Buying back shares"
             + (f" (count {sh:+.1f}% on a year ago)" if sh is not None else ""))
    if cash is not None or debt is not None:
        net = (debt or 0.0) - (cash or 0.0)
        flag("balance", "good" if net <= 0 else "neutral",
             f"Net cash of {money(-net)}" if net <= 0 else f"Net debt of {money(net)}")

    notes: list[str] = []
    deferred = q.get("deferred_change")
    if deferred and cfo and cfo > 0 and deferred >= DEFERRED_SHARE * cfo:
        notes.append(f"Customers paying ahead added {money(deferred)}, "
                     f"{100 * deferred / cfo:.0f}% of operating cash flow; without it "
                     f"operating cash flow was {money(cfo - deferred)}.")
    sbc = q.get("sbc")
    if sbc and cfo and cfo > 0 and sbc >= SBC_SHARE * cfo:
        notes.append(f"Stock compensation of {money(sbc)} is {100 * sbc / cfo:.0f}% of "
                     f"operating cash flow, which it is added back into.")
    dna = q.get("dna")
    if dna and rev and dna >= DNA_SHARE * rev:
        notes.append(f"Depreciation and amortisation is {100 * dna / rev:.0f}% of revenue"
                     + (f", against a gross margin of {gm:.0f}%." if gm is not None else "."))
    if capex and rev and capex >= CAPEX_SHARE * rev:
        last4 = quarters[-4:]
        total_capex = sum(abs(x.get("capex") or 0.0) for x in last4)
        total_rev = sum(x.get("revenue") or 0.0 for x in last4)
        notes.append(f"Capital spending is {100 * capex / rev:.0f}% of revenue; "
                     f"{money(total_capex)} over four quarters against "
                     f"{money(total_rev)} of revenue.")
    prev_debt = prev.get("debt")
    if debt and prev_debt and debt >= prev_debt * (1 + DEBT_JUMP):
        notes.append(f"Debt rose {100 * (debt / prev_debt - 1):.0f}% on the quarter, "
                     f"to {money(debt)}.")
    interest, op = q.get("interest"), q.get("op_income")
    if interest and op is not None:
        if op > 0 and interest >= INTEREST_SHARE * op:
            notes.append(f"Interest of {money(interest)} takes {100 * interest / op:.0f}% "
                         f"of operating income.")
        elif op <= 0:
            notes.append(f"Interest of {money(interest)} on top of an operating loss.")
    rpo = q.get("rpo")
    last4 = quarters[-4:]
    ttm_rev = sum(x.get("revenue") or 0.0 for x in last4) if len(last4) == 4 else None
    if rpo and ttm_rev and rpo >= BACKLOG_SHARE * ttm_rev:
        notes.append(f"Contracted backlog of {money(rpo)}, {rpo / ttm_rev:.1f} times "
                     f"twelve months' revenue. Backlog is not yet revenue.")

    bars = [{"end": x["end"], "revenue": x.get("revenue"), "fcf": x.get("fcf"),
             "net_income": x.get("net_income")} for x in quarters[-SHOWN:]]
    return {"glance": glance, "flags": flags, "notes": notes, "bars": bars}
