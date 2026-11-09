"""Earnings reads: a reporter's quarter as measured lines, with a rules read.

Ported from Market Desk's coordinator/earnings_read.py, line for line where
the inputs match, and fed from the quarters data/fundamentals.py keeps from
each company's XBRL filings. For the latest quarter beside the one before it
and the same quarter a year earlier:

  at a glance   revenue with its change on the quarter and the year; gross
                margin and its move in points; operating and net income;
                operating and free cash flow against the prior quarter; the
                share count against a year earlier; cash, debt and, when free
                cash flow is negative, the runway in quarters at that burn
  flags         fixed rules on those numbers, each with its tone
  not obvious   what the same filing shows that a headline does not, only
                past a threshold: a deferred-revenue inflow carrying cash
                flow, stock pay added back, depreciation against margin,
                capital intensity, debt up on the quarter, interest against
                operating income, contracted backlog
  takeaway      one sentence chosen by the pattern of the flags
  final read    growth REAL / WEAK / FLAT and economic proof SHOWN / PENDING,
                with the question those imply and the first weak flag named
                as what the next quarter has to show
  the desk      the EPS surprise, the move on the print against what the
                chain priced, and any drift signal since, from Market Desk

A 10-Q lands days or weeks after the release. Until it does the card is the
prior quarter and says so. Every line is a rule on filed numbers; nothing
here reads the release text, and none of it enters a screen or a rating.
"""
from __future__ import annotations

import datetime as dt

READ_DAYS = 35           # reporters this far back get a card on the Earnings page
STALE_DAYS = 200         # a newest quarter this old before the report is not current
COVER_DAYS = 100         # a quarter ending within this of the report is the one reported
GROWTH_STRONG = 20.0     # revenue year over year, %
GROWTH_WEAK = -5.0
MARGIN_PP = 1.0          # gross margin move that counts, points
DILUTION_PCT = 5.0       # share count year over year, %
DEFERRED_SHARE = 0.25    # of operating cash flow
SBC_SHARE = 0.5          # of operating cash flow
DNA_SHARE = 0.10         # of revenue
CAPEX_SHARE = 0.5        # of revenue
DEBT_JUMP = 10.0         # % on the quarter
SHOWN = 8                # quarters drawn as bars


def money(v: float | None) -> str:
    if v is None:
        return "—"
    a, sign = abs(v), "-" if v < 0 else ""
    if a >= 1e9:
        return f"{sign}${a / 1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.0f}M"
    if a >= 1e3:
        return f"{sign}${a / 1e3:.0f}K"
    return f"{sign}${a:.0f}"


def _qtrs(q: float) -> str:
    n = round(q)
    return "under one quarter" if n < 1 else "1 quarter" if n == 1 else f"{n} quarters"


def _pct(a, b) -> float | None:
    return None if a is None or not b or b <= 0 else round((a / b - 1) * 100, 1)


def _margin(part, whole) -> float | None:
    return None if part is None or not whole else round(100 * part / whole, 1)


def _date(iso: str) -> dt.date:
    return dt.date.fromisoformat(iso)


def _year_ago(quarters: list[dict], i: int) -> dict | None:
    end = _date(quarters[i]["end"])
    for q in reversed(quarters[:i]):
        if abs((end - _date(q["end"])).days - 364) <= 21:
            return q
    return None


def glance(Q: list[dict]) -> dict | None:
    """The at-a-glance numbers from the quarters, oldest first."""
    if not Q:
        return None
    q0, q1 = Q[-1], (Q[-2] if len(Q) > 1 else None)
    qy = _year_ago(Q, len(Q) - 1)
    # Share counts are three-month weighted averages, so a fiscal fourth
    # quarter worked out from the year has none: the latest quarter that does
    # stands in, when it is the quarter before.
    counted = [x for x in Q if x.get("shares")]
    latest = counted[-1] if counted else None
    if latest and (_date(q0["end"]) - _date(latest["end"])).days > 100:
        latest = None
    shares_ago = _year_ago(counted, len(counted) - 1) if latest else None
    g = {
        "end": q0["end"], "revenue": q0.get("revenue"),
        "rev_qoq": _pct(q0.get("revenue"), (q1 or {}).get("revenue")),
        "rev_yoy": _pct(q0.get("revenue"), (qy or {}).get("revenue")),
        "gm": _margin(q0.get("gross_profit"), q0.get("revenue")),
        "gm_prev": _margin(q1.get("gross_profit"), q1.get("revenue")) if q1 else None,
        "op_income": q0.get("op_income"),
        "op_margin": _margin(q0.get("op_income"), q0.get("revenue")),
        "net_income": q0.get("net_income"),
        "net_prev": (q1 or {}).get("net_income"),
        "cfo": q0.get("cfo"), "capex": q0.get("capex"),
        "fcf": q0.get("fcf"), "fcf_prev": (q1 or {}).get("fcf"),
        "dilution": _pct((latest or {}).get("shares"), (shares_ago or {}).get("shares")),
        "cash": q0.get("cash"), "debt": q0.get("debt"),
    }
    g["gm_pp"] = (None if g["gm"] is None or g["gm_prev"] is None
                  else round(g["gm"] - g["gm_prev"], 1))
    g["runway_q"] = (round(g["cash"] / -g["fcf"], 1)
                     if g["fcf"] is not None and g["fcf"] < 0 and g["cash"] else None)
    g["net_cash"] = (None if g["cash"] is None and g["debt"] is None
                     else (g["cash"] or 0) - (g["debt"] or 0))
    return g


def flags(g: dict | None) -> list[dict]:
    """[{key, tone, text}] from fixed rules. tone: 1 good, -1 bad, 0 neutral."""
    out: list[dict] = []
    if g is None:
        return out
    m = money
    if g["rev_yoy"] is not None:
        t = 1 if g["rev_yoy"] >= GROWTH_STRONG else -1 if g["rev_yoy"] <= GROWTH_WEAK else 0
        out.append({"key": "growth", "tone": t,
                    "text": f"Revenue {g['rev_yoy']:+.1f}% year over year"
                            + (f", {g['rev_qoq']:+.1f}% on the quarter" if g["rev_qoq"] is not None else "")})
    elif g["rev_qoq"] is not None:
        t = 1 if g["rev_qoq"] >= 10 else -1 if g["rev_qoq"] <= -5 else 0
        out.append({"key": "growth", "tone": t,
                    "text": f"Revenue {g['rev_qoq']:+.1f}% on the quarter (no year-earlier quarter on file)"})
    if g["gm_pp"] is not None:
        t = 1 if g["gm_pp"] >= MARGIN_PP else -1 if g["gm_pp"] <= -MARGIN_PP else 0
        out.append({"key": "margin", "tone": t,
                    "text": f"Gross margin {g['gm']:.1f}%, {g['gm_pp']:+.1f} points on the quarter"})
    elif g["gm"] is not None:
        out.append({"key": "margin", "tone": 0 if g["gm"] >= 0 else -1,
                    "text": f"Gross margin {g['gm']:.1f}%"})
    ni, op, prev = g["net_income"], g["op_income"], g["net_prev"]
    if ni is not None:
        if ni > 0 and (op is None or op > 0):
            out.append({"key": "profit", "tone": 1,
                        "text": f"Profitable: net income {m(ni)}"
                                + (f", operating margin {g['op_margin']:.1f}%" if g["op_margin"] is not None else "")})
        elif ni > 0:
            out.append({"key": "profit", "tone": 0,
                        "text": f"Net income {m(ni)} on an operating loss of {m(abs(op))}: "
                                "below the line, not operations"})
        else:
            tail = ""
            if prev is not None and prev < ni < 0:
                tail = f", narrower than {m(abs(prev))} last quarter"
            elif prev is not None and ni < prev < 0:
                tail = f", wider than {m(abs(prev))} last quarter"
            out.append({"key": "profit", "tone": -1, "text": f"Net loss {m(abs(ni))}{tail}"})
    if g["fcf"] is not None:
        if g["fcf"] > 0 and (g["cfo"] or 0) > 0:
            out.append({"key": "cash", "tone": 1,
                        "text": f"Cash generating: operating cash flow {m(g['cfo'])}, "
                                f"free cash flow {m(g['fcf'])}"})
        else:
            before = g["fcf_prev"]
            trend = ("" if before is None
                     else f", worse than {m(before)} last quarter" if g["fcf"] < before
                     else f", better than {m(before)} last quarter")
            runway = (f" · {_qtrs(g['runway_q'])} of cash at this burn"
                      if g["runway_q"] is not None and g["runway_q"] < 40 else "")
            out.append({"key": "cash", "tone": -1,
                        "text": f"Burning cash: operating cash flow {m(g['cfo'])}, "
                                f"free cash flow {m(g['fcf'])}{trend}{runway}"})
    capex, cfo, dil = g["capex"], g["cfo"], g["dilution"]
    if capex is not None and cfo is not None and abs(capex) > max(cfo, 0):
        text = f"Growth externally funded: capex {m(abs(capex))} against operating cash flow {m(cfo)}"
        if dil is not None and dil >= DILUTION_PCT:
            text += f"; share count {dil:+.1f}% in a year"
        out.append({"key": "funding", "tone": -1, "text": text})
    elif dil is not None and dil >= DILUTION_PCT:
        out.append({"key": "funding", "tone": -1, "text": f"Share count {dil:+.1f}% in a year: dilution"})
    elif dil is not None and dil <= -2:
        out.append({"key": "funding", "tone": 1, "text": f"Share count {dil:+.1f}% in a year: buying back"})
    if g["net_cash"] is not None:
        nc = g["net_cash"]
        out.append({"key": "balance",
                    "tone": 1 if nc > 0 else -1 if nc < -(g["revenue"] or 0) * 2 else 0,
                    "text": (f"Net cash {m(nc)}" if nc >= 0 else f"Net debt {m(-nc)}")
                            + (f" · cash {m(g['cash'])}" if g["cash"] is not None else "")})
    return out


def forensic(Q: list[dict], g: dict | None) -> list[dict]:
    """[{key, tone, text}]: what the headline numbers do not show, from the
    same filing. Only lines the thresholds make worth saying."""
    out: list[dict] = []
    if not Q or g is None:
        return out
    m = money
    q0, q1 = Q[-1], (Q[-2] if len(Q) > 1 else None)
    cfo, rev = q0.get("cfo"), q0.get("revenue") or 0
    last4 = Q[-4:]
    rev_ttm = sum(q.get("revenue") or 0 for q in last4) if len(last4) == 4 else None
    dd = q0.get("deferred_change")
    if cfo is not None and dd is not None and dd > 0 and dd >= DEFERRED_SHARE * max(cfo, 1):
        out.append({"key": "deferred", "tone": -1,
                    "text": f"Cash flow quality: operating cash flow {m(cfo)} included a {m(dd)} "
                            f"deferred-revenue inflow; {m(cfo - dd)} without it. "
                            "Customers paid ahead of delivery"})
    sbc = q0.get("sbc")
    if cfo is not None and sbc is not None and sbc > 0 and (cfo <= 0 or sbc >= SBC_SHARE * cfo):
        out.append({"key": "sbc", "tone": -1,
                    "text": f"Stock compensation {m(sbc)} added back"
                            + (f", {100 * sbc / cfo:.0f}% of operating cash flow; {m(cfo - sbc)} after it"
                               if cfo > 0 else " against negative operating cash flow")})
    dna = q0.get("dna")
    if dna is not None and rev and dna >= DNA_SHARE * rev and g.get("gm") is not None:
        out.append({"key": "dna", "tone": 0,
                    "text": f"Margin quality: depreciation and amortisation {m(dna)} is "
                            f"{100 * dna / rev:.0f}% of revenue; gross margin {g['gm']:.1f}% reads "
                            f"{100 * ((q0.get('gross_profit') or 0) - dna) / rev:.1f}% if it is charged there"})
    capex = abs(q0.get("capex") or 0)
    if capex and rev and capex >= CAPEX_SHARE * rev:
        capex_ttm = sum(abs(q.get("capex") or 0) for q in last4) if len(last4) == 4 else None
        text = f"Capital intensity: {m(capex)} of capex on {m(rev)} of revenue this quarter"
        if capex_ttm and rev_ttm:
            text += f", {m(capex_ttm)} over four quarters ({capex_ttm / rev_ttm:.1f}× revenue)"
        if cfo is not None and capex > max(cfo, 0):
            text += ". Expansion is not self-funded"
        out.append({"key": "capex", "tone": -1, "text": text})
    debt = q0.get("debt")
    if debt and q1 and q1.get("debt"):
        change = (debt / q1["debt"] - 1) * 100
        if change >= DEBT_JUMP:
            out.append({"key": "debt", "tone": -1,
                        "text": f"Debt {m(debt)}, {change:+.0f}% on the quarter"
                                + (f"; {debt / rev_ttm:.1f}× trailing revenue" if rev_ttm else "")})
    interest, op = q0.get("interest"), q0.get("op_income")
    if interest and interest > 0 and op is not None:
        if op <= 0:
            out.append({"key": "interest", "tone": -1,
                        "text": f"Interest {m(interest)} a quarter against an operating loss: "
                                "the debt is carried by the balance sheet, not operations"})
        elif interest >= 0.5 * op:
            out.append({"key": "interest", "tone": -1,
                        "text": f"Interest {m(interest)} takes {100 * interest / op:.0f}% of "
                                f"operating income {m(op)}"})
    rpo = q0.get("rpo")
    # Desk shows any backlog; one under a tenth of a year's revenue printed
    # as "0.0× trailing revenue", which says nothing.
    if rpo and rev_ttm and rpo >= 0.1 * rev_ttm:
        prev = (q1 or {}).get("rpo")
        out.append({"key": "backlog", "tone": 0,
                    "text": f"Contracted backlog (remaining performance obligations) {m(rpo)}, "
                            f"{rpo / rev_ttm:.1f}× trailing revenue"
                            + (f", {(rpo / prev - 1) * 100:+.0f}% on the quarter" if prev else "")
                            + ". Backlog is not recognised revenue"})
    return out


def verdict(F: list[dict], X: list[dict]) -> dict:
    """The two-word final read: growth and economic proof, from the flags."""
    t = {f["key"]: f["tone"] for f in F}
    x = {f["key"] for f in X}
    g = t.get("growth")
    growth = "REAL" if g == 1 else "WEAK" if g == -1 else "FLAT"
    proof = ("SHOWN" if t.get("cash") == 1 and t.get("profit") == 1
             and not ({"deferred", "sbc"} & x) else "PENDING")
    # Market Desk's questions, plus one: profit and cash both in place but
    # carried by customers paying ahead or by stock pay fell through to "what
    # turns the cash flow positive?", which is wrong about a positive figure.
    question = (
        "Can the growth turn into durable profit and cash after its costs and financing?"
        if g == 1 and proof == "PENDING" else
        "Does the cash flow hold without the deferred revenue and stock pay behind it?"
        if t.get("cash") == 1 and t.get("profit") == 1 and proof == "PENDING" else
        "Can the recovery in margins reach operating profit and cash?"
        if t.get("margin") == 1 and t.get("profit") == -1 else
        "Can the cash generation hold as growth slows?" if proof == "SHOWN" and g != 1 else
        "Does the next quarter repeat this one?" if proof == "SHOWN" else
        "What turns the cash flow positive?")
    return {"growth": growth, "proof": proof, "question": question}


def takeaway(F: list[dict]) -> str:
    """One sentence from the pattern of flags."""
    t = {f["key"]: f["tone"] for f in F}
    g, mg, p, c, fu = (t.get("growth"), t.get("margin"), t.get("profit"),
                       t.get("cash"), t.get("funding"))
    if g == 1 and c == 1 and mg != -1:
        return "Growth with the cash to show for it: the quarter confirms the thesis."
    if g == 1 and (c == -1 or fu == -1):
        return "Real growth, but execution and cash generation are not yet proven."
    if g == 1 and mg == -1:
        return "Growth at the cost of margin: demand is there, pricing or mix is not."
    if mg == 1 and p == -1:
        return "Margins are improving, but the financial turnaround is not yet proven."
    if g == -1 and c == -1:
        return "Shrinking and burning cash: the quarter weakens the case."
    if g == -1 and c == 1:
        return "Revenue is falling but the business still generates cash."
    if c == 1 and p == 1:
        return "Profitable and cash generating; the question is growth."
    if c == -1:
        return "Cash flow is the weak point of the quarter."
    return "A mixed quarter: the numbers do not agree."


def the_test(F: list[dict]) -> str:
    first = next((f for f in F if f["tone"] == -1), None)
    names = {"growth": "revenue growth", "margin": "gross margin", "profit": "operating profit",
             "cash": "cash generation", "funding": "funding the growth from operations",
             "balance": "the balance sheet"}
    if not first:
        return "The next test is whether the quarter repeats."
    return (f"The next test is {names.get(first['key'], first['key'])}: "
            + first["text"][0].lower() + first["text"][1:] + ".")


def read(quarters: list[dict] | None, report_date: str | None = None,
         desk: dict | None = None) -> dict | None:
    """The full read of the latest quarter, or None with nothing to read.

    With a report date, None when the newest quarter is too old to be the
    company's current reporting, and `covers` says whether the quarter on
    file is the one reported or the one before it.
    """
    if not quarters or len(quarters) < 2:
        return None
    g = glance(quarters)
    covers = None
    if report_date:
        age = (_date(report_date) - _date(g["end"])).days
        if age > STALE_DAYS:
            return None
        covers = age <= COVER_DAYS
    F = flags(g)
    X = forensic(quarters, g)
    return {
        "report_date": report_date, "covers": covers,
        "glance": g, "flags": F, "forensic": X,
        "takeaway": takeaway(F), "verdict": verdict(F, X), "test": the_test(F),
        "desk": desk or None,
        "bars": [{"end": q["end"], "revenue": q.get("revenue"), "fcf": q.get("fcf"),
                  "net_income": q.get("net_income")} for q in quarters[-SHOWN:]],
    }


def desk_line(symbol: str, report_date: str, settled: list[dict],
              signals: list[dict]) -> dict | None:
    """What Market Desk measured around this print: the EPS surprise, the
    move against the priced move, and a drift signal since."""
    out: dict = {}
    row = next((r for r in settled if (r.get("ticker") or "").upper() == symbol
                and r.get("report_date") == report_date), None)
    if row:
        for key in ("surprise_pct", "implied_pct", "realised_pct"):
            if row.get(key) is not None:
                out[key] = row[key]
    drift = sorted((s for s in signals
                    if (s.get("reason") or "").upper() in ("PEAD_UP", "PEAD_DOWN")
                    and (s.get("as_of") or "") >= report_date),
                   key=lambda s: s["as_of"])
    if drift:
        out["drift"] = drift[0]["reason"].upper()
        out["drift_date"] = drift[0]["as_of"]
    return out or None


def build(filed: dict[str, dict | None], reported: dict[str, list[dt.date]],
          as_of: dt.date, settled: list[dict] | None = None,
          signals: dict[str, list[dict]] | None = None) -> list[dict]:
    """A read for every company that reported in the last READ_DAYS and has
    quarters on file, newest report first."""
    out = []
    since = as_of - dt.timedelta(days=READ_DAYS)
    for symbol, dates in reported.items():
        recent = [d for d in dates if since <= d <= as_of]
        payload = filed.get(symbol)
        if not recent or not payload or not payload.get("quarters"):
            continue
        rd = max(recent).isoformat()
        card = read(payload["quarters"], rd,
                    desk_line(symbol, rd, settled or [], (signals or {}).get(symbol) or []))
        if card:
            out.append({"symbol": symbol, **card})
    out.sort(key=lambda r: (r["report_date"], r["symbol"]), reverse=True)
    return out
