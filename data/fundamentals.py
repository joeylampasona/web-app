"""Trailing-twelve-month fundamentals from each company's own XBRL filings.

Revenue and its growth, margins, free cash flow and the balance sheet, read
from SEC's companyfacts file for the company. Ported from Market Desk's
scanners/fundamentals.py, which computes the same figures for its own ranked
names; here it covers the whole universe.

Flows (revenue, income, cash flow) are summed over the last four quarterly
frames; growth compares the latest quarter with the same quarter a year
earlier; balance items take the latest instant. A filer that reports under
IFRS rather than US GAAP -- most foreign listings -- has no us-gaap frames and
gets nothing, which is stored as nothing so it is not asked again every night.

Each company is refreshed every REFRESH_DAYS, since the inputs change
quarterly, and at most BUDGET a night, most traded first, so the first week
after this ships fills the universe in rather than spending an hour on it.
Context on the stock page; never part of a screen.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sqlite3
import time
from typing import Iterable

import requests

from data import edgar, settings

log = logging.getLogger(__name__)

REFRESH_DAYS = 30
BUDGET = 400
DUE_DAYS = 40
COVERED_DAYS = 75
IFRAME = re.compile(r"^CY(\d{4})Q([1-4])I$")

# Candidate concepts, freshest series wins. Flows are summed over four quarters.
FLOWS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax",
                "TotalRevenuesAndOtherIncome"],
    "gross_profit": ["GrossProfit"],
    "op_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment",
              "PaymentsToAcquireProductiveAssets"],
}
# Read only for the quarter-by-quarter view and its forensic lines; none of
# these enters a trailing total.
EXTRA_FLOWS = {
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "dna": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet", "Depreciation"],
    "interest": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    # Cash-flow line: positive when customers paid ahead of the revenue.
    "deferred_change": ["IncreaseDecreaseInContractWithCustomerLiability",
                        "IncreaseDecreaseInDeferredRevenue"],
    "buyback": ["PaymentsForRepurchaseOfCommonStock"],
}
SHARES = ["WeightedAverageNumberOfDilutedSharesOutstanding",
          "WeightedAverageNumberOfSharesOutstandingBasic"]
QUARTER_INSTANTS = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "lt_debt": ["LongTermDebtNoncurrent", "LongTermDebt",
                "LongTermDebtAndCapitalLeaseObligations"],
    "st_debt": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"],
    "rpo": ["RevenueRemainingPerformanceObligation"],
}
QUARTERS_KEPT = 10

INSTANTS = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "lt_debt": ["LongTermDebtNoncurrent", "LongTermDebt",
                "LongTermDebtAndCapitalLeaseObligations"],
    "st_debt": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}


def _frames(facts: dict, concepts: list[str], rx, min_rows: int) -> dict:
    """{(year, quarter): value} from the candidate concept whose frames run
    latest. Used for balance-sheet instants, which every 10-Q and 10-K carry
    at its own period end, so the calendar frames are complete for them."""
    best: dict = {}
    best_key = None
    for concept in concepts:
        node = (facts.get("us-gaap") or {}).get(concept)
        if not node:
            continue
        for rows in (node.get("units") or {}).values():
            found = {}
            for row in rows:
                m = rx.match(row.get("frame") or "")
                if m:
                    try:
                        found[(int(m.group(1)), int(m.group(2)))] = float(row["val"])
                    except (TypeError, ValueError, KeyError):
                        continue
            if len(found) >= min_rows and (best_key is None or max(found) > best_key):
                best, best_key = found, max(found)
    return best


def _date(text) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None


def _durations(facts: dict, concepts: list[str],
               unit: str = "USD") -> list[tuple[dt.date, dt.date, float]]:
    """Every (start, end, value) for the candidate concept whose figures run
    latest, in dollars, one per period (the most recently filed wins, so a
    restatement replaces the original). Companies retire concepts -- Apple's
    "Revenues" stops in 2018 -- so the first with data is not the right one.
    """
    best: list = []
    best_end = None
    for concept in concepts:
        node = (facts.get("us-gaap") or {}).get(concept)
        if not node:
            continue
        rows = (node.get("units") or {}).get(unit) or []
        latest: dict = {}
        for row in rows:
            start, end = _date(row.get("start")), _date(row.get("end"))
            if not (start and end) or end <= start:
                continue
            try:
                value = float(row["val"])
            except (TypeError, ValueError, KeyError):
                continue
            filed = str(row.get("filed") or "")
            held = latest.get((start, end))
            if held is None or filed >= held[0]:
                latest[(start, end)] = (filed, value)
        if latest:
            newest = max(end for _, end in latest)
            if best_end is None or newest > best_end:
                best = [(s, e, v) for (s, e), (_, v) in latest.items()]
                best_end = newest
    return best


def _instants(facts: dict, concepts: list[str]) -> dict[dt.date, float]:
    """{period end: value} for a balance-sheet item, from the candidate concept
    whose figures run latest; the most recently filed wins for each date."""
    best: dict = {}
    for concept in concepts:
        node = (facts.get("us-gaap") or {}).get(concept)
        if not node:
            continue
        latest: dict = {}
        for row in (node.get("units") or {}).get("USD") or []:
            end = _date(row.get("end"))
            if not end or row.get("start"):
                continue
            try:
                value = float(row["val"])
            except (TypeError, ValueError, KeyError):
                continue
            filed = str(row.get("filed") or "")
            if end not in latest or filed >= latest[end][0]:
                latest[end] = (filed, value)
        if latest and (not best or max(latest) > max(best)):
            best = {e: v for e, (_, v) in latest.items()}
    return best


def _near(values: dict, end: dt.date, days: int = 7):
    """The value filed for a date within `days` of end, or None."""
    for when, value in values.items():
        if abs((when - end).days) <= days:
            return value
    return None


def quarterly(facts: dict, keep: int = QUARTERS_KEPT) -> list[dict]:
    """The last `keep` quarters, oldest first, each with its flows and the
    balance sheet at its end. Every figure is None where the filing has none.

    Revenue sets the quarters; each other line is matched to them by end
    date. Share counts are weighted averages, which neither difference nor
    subtract from a year, so they come from three-month periods only and the
    fiscal fourth quarter has none.
    """
    revenue = _quarters(_durations(facts, FLOWS["revenue"]))[-keep:]
    if not revenue:
        return []
    lines = {key: {e: v for _, e, v in _quarters(_durations(facts, concepts))}
             for key, concepts in {**FLOWS, **EXTRA_FLOWS}.items() if key != "revenue"}
    shares = {e: v for s, e, v in _durations(facts, SHARES, unit="shares")
              if 80 <= (e - s).days <= 100}
    balances = {key: _instants(facts, concepts)
                for key, concepts in QUARTER_INSTANTS.items()}
    out = []
    for start, end, value in revenue:
        row: dict = {"start": start.isoformat(), "end": end.isoformat(), "revenue": value}
        for key, values in lines.items():
            row[key] = _near(values, end)
        row["shares"] = _near(shares, end)
        for key, values in balances.items():
            row[key] = _near(values, end)
        cfo, capex = row.get("cfo"), row.get("capex")
        row["fcf"] = None if cfo is None else cfo - abs(capex or 0.0)
        lt, st = row.pop("lt_debt"), row.pop("st_debt")
        row["debt"] = None if lt is None and st is None else (lt or 0.0) + (st or 0.0)
        out.append(row)
    return out


def _quarters(durations) -> list[tuple[dt.date, dt.date, float]]:
    """Three-month periods in date order, with the fiscal fourth quarter filled
    in from the annual figure.

    Companies file three 10-Qs and a 10-K, so the fourth quarter appears only
    inside the year. Summing "the last four quarters on file" therefore skips
    it and reaches back a year for a substitute -- the figure Market Desk's
    version of this computes. Here the missing quarter is the annual total
    less the three quarters filed inside that year.
    """
    quarters = {e: (s, v) for s, e, v in durations if 80 <= (e - s).days <= 100}
    # Cash-flow statements are year-to-date in every 10-Q: six months, then
    # nine. Successive figures from the same fiscal-year start differ by one
    # quarter, so each quarter is the difference. Filed three-month figures
    # win where both exist.
    by_start: dict = {}
    for s, e, v in durations:
        by_start.setdefault(s, []).append((e, v))
    for s, rows in by_start.items():
        rows.sort()
        for (prev_end, prev_val), (end, val) in zip(rows, rows[1:]):
            if 80 <= (end - prev_end).days <= 100 and not any(
                    abs((qe - end).days) <= 7 for qe in quarters):
                quarters[end] = (prev_end + dt.timedelta(days=1), val - prev_val)
    for s, e, v in durations:
        if not 350 <= (e - s).days <= 380:
            continue
        if any(abs((qe - e).days) <= 7 for qe in quarters):
            continue
        inside = [(qs, qe, qv) for qe, (qs, qv) in quarters.items()
                  if qs >= s - dt.timedelta(days=7) and qe <= e + dt.timedelta(days=7)]
        if len(inside) != 3:
            continue
        last_end = max(qe for _, qe, _ in inside)
        quarters[e] = (last_end + dt.timedelta(days=1), v - sum(qv for _, _, qv in inside))
    return sorted(((s, e, v) for e, (s, v) in quarters.items()), key=lambda q: q[1])


def _ttm(quarters):
    """(trailing four-quarter sum, latest quarter's end, year-on-year growth %).

    The sum only when the four quarters run back to back; a gap means a filing
    is missing and the total would be a different twelve months.
    """
    if not quarters:
        return None, None, None
    last_end = quarters[-1][1]
    if len(quarters) < 4:
        return None, last_end, None
    four = quarters[-4:]
    if any(not 0 <= (four[i][0] - four[i - 1][1]).days <= 7 for i in range(1, 4)):
        return None, last_end, None
    total = sum(v for _, _, v in four)
    latest = four[-1][2]
    prior = next((v for _, e, v in reversed(quarters[:-1])
                  if abs((last_end - e).days - 364) <= 21), None)
    growth = (round((latest / prior - 1) * 100, 1)
              if prior and prior > 0 else None)
    return total, last_end, growth


def parse(doc: dict, today: dt.date | None = None) -> dict | None:
    """The figures from a companyfacts document, or None without revenue.

    None too when the newest quarter ended over a year and a half ago: a
    company that stopped filing in US GAAP should show nothing rather than
    its numbers from 2019 as if current.
    """
    today = today or dt.date.today()
    facts = doc.get("facts") or {}
    rev_ttm, last_end, rev_growth = _ttm(_quarters(_durations(facts, FLOWS["revenue"])))
    if rev_ttm is None or last_end is None:
        return None
    if (today - last_end).days > 550:
        return None
    out: dict = {"period_end": last_end.isoformat(), "revenue_ttm": rev_ttm,
                 "revenue_growth": rev_growth}
    for key in ("gross_profit", "op_income", "net_income", "cfo", "capex"):
        total, end, _ = _ttm(_quarters(_durations(facts, FLOWS[key])))
        # Only a total for the same twelve months as revenue; a margin built
        # from two different years is not a margin.
        out[f"{key}_ttm"] = total if end == last_end else None
    for key, concepts in INSTANTS.items():
        inst = _frames(facts, concepts, IFRAME, 1)
        out[key] = inst[max(inst)] if inst else None
    rev = rev_ttm or 0.0

    def margin(value):
        return round(100.0 * value / rev, 1) if value is not None and rev else None

    out["gross_margin"] = margin(out["gross_profit_ttm"])
    out["op_margin"] = margin(out["op_income_ttm"])
    out["net_margin"] = margin(out["net_income_ttm"])
    cfo, capex = out["cfo_ttm"], out["capex_ttm"]
    out["fcf_ttm"] = None if cfo is None else cfo - abs(capex or 0.0)
    debt = (out["lt_debt"] or 0.0) + (out["st_debt"] or 0.0)
    out["net_debt"] = (None if out["cash"] is None and not debt
                       else debt - (out["cash"] or 0.0))
    # Only what a page shows; the intermediate concepts stay here.
    keep = ("period_end", "revenue_ttm", "revenue_growth", "gross_margin", "op_margin",
            "net_margin", "net_income_ttm", "fcf_ttm", "cash", "net_debt", "equity")
    figures = {k: out[k] for k in keep}
    figures["quarters"] = quarterly(facts)
    return figures


def stale(conn: sqlite3.Connection, symbols: Iterable[str],
          max_age_days: int = REFRESH_DAYS) -> list[str]:
    """The symbols with no row, or a row older than the refresh window, in order.

    A row stored before the quarter-by-quarter figures existed counts as stale
    too, so the universe picks them up over the nights after they ship
    without waiting a month for each company to age out.
    """
    fresh = {row["symbol"] for row in conn.execute(
        "SELECT symbol FROM fundamentals_xbrl WHERE fetched_at > datetime('now', ?)"
        " AND (payload = 'null' OR payload LIKE '%\"quarters\"%')",
        (f"-{int(max_age_days)} days",))}
    return [s for s in symbols if s not in fresh]


def due(conn: sqlite3.Connection, reported: dict[str, list[dt.date]],
        today: dt.date | None = None) -> list[str]:
    """Companies that reported in the last DUE_DAYS whose stored figures end a
    quarter before the report, and that were not already asked today.

    A 10-Q lands within days of the print, so these are asked every night
    until the quarter it covers is stored, rather than once a month.
    """
    today = today or dt.date.today()
    held = {row["symbol"]: (row["fetched_at"], row["payload"]) for row in conn.execute(
        "SELECT symbol, fetched_at, payload FROM fundamentals_xbrl")}
    out = []
    for symbol, dates in reported.items():
        recent = [d for d in dates if 0 <= (today - d).days <= DUE_DAYS]
        if not recent:
            continue
        report = max(recent)
        fetched, payload = held.get(symbol, (None, None))
        if fetched and str(fetched)[:10] >= today.isoformat():
            continue
        try:
            end = _date((json.loads(payload or "null") or {}).get("period_end"))
        except (TypeError, ValueError, AttributeError):
            end = None
        if fetched and end is None:
            # Asked before and nothing in US GAAP: a foreign filer does not
            # start filing 10-Qs because it reported.
            continue
        # A report covers the quarter that ended up to about ten weeks before
        # it; anything older is the quarter before.
        if end is None or (report - end).days > COVERED_DAYS:
            out.append(symbol)
    return out


def refresh(conn: sqlite3.Connection, symbols: Iterable[str], budget: int = BUDGET,
            notice=None, first: Iterable[str] = ()) -> dict:
    """Fetch and store fundamentals for up to `budget` stale symbols, in the
    order given (callers pass most traded first), after any in `first`: the
    recent reporters, asked whatever their age. Never raises on one company;
    raises EdgarUnavailable only when SEC cannot be reached at all."""
    if settings.get("data.provider") == "synthetic":
        return {"asked": 0, "stored": 0, "empty": 0, "remaining": 0}
    symbols = [s.upper() for s in symbols]
    ahead = [s.upper() for s in first if s.upper() in set(symbols)]
    wanted = list(dict.fromkeys(ahead + stale(conn, symbols)))
    ask = wanted[:budget]
    session = requests.Session()
    cik_map = edgar._ticker_to_cik(session)
    base = (settings.get("edgar.base_url") or "https://data.sec.gov").rstrip("/")
    stored = empty = refused = 0
    for index, symbol in enumerate(ask, 1):
        if notice and index % 100 == 0:
            notice(f"  fundamentals {index}/{len(ask)}")
        cik = next((cik_map[n] for n in edgar._cik_candidates(symbol) if n in cik_map), None)
        payload = None
        if cik:
            try:
                resp = session.get(f"{base}/api/xbrl/companyfacts/{cik}.json",
                                   headers={"User-Agent": edgar._user_agent()}, timeout=60)
                time.sleep(edgar.REQUEST_PAUSE)
                if resp.status_code in edgar.THROTTLE_STATUSES:
                    # Not stored: a refusal is about us, and the company
                    # should be asked again tomorrow, not in a month.
                    refused += 1
                    time.sleep(edgar.THROTTLE_PAUSE)
                    continue
                if resp.status_code == 200:
                    payload = parse(resp.json())
            except Exception as exc:                   # noqa: BLE001
                log.debug("fundamentals failed for %s: %s", symbol, exc)
                continue
        conn.execute(
            "INSERT OR REPLACE INTO fundamentals_xbrl(symbol, fetched_at, payload)"
            " VALUES (?, datetime('now'), ?)", (symbol, json.dumps(payload)))
        if payload:
            stored += 1
        else:
            empty += 1
        if index % 50 == 0:
            conn.commit()
    conn.commit()
    if ask and refused == len(ask):
        raise edgar.EdgarUnavailable(
            f"SEC refused all {refused} fundamentals requests tonight.")
    return {"asked": len(ask), "stored": stored, "empty": empty,
            "refused": refused, "remaining": max(0, len(wanted) - len(ask))}


def load(conn: sqlite3.Connection) -> dict[str, dict | None]:
    """Every company asked about, by symbol: its figures, or None when SEC had
    nothing usable. A symbol not asked yet is absent, which is different: the
    page hides the section rather than saying the company files nothing."""
    out: dict[str, dict | None] = {}
    for row in conn.execute("SELECT symbol, payload FROM fundamentals_xbrl"):
        try:
            payload = json.loads(row["payload"] or "null")
        except (TypeError, ValueError):
            payload = None
        out[row["symbol"]] = payload if isinstance(payload, dict) else None
    return out
