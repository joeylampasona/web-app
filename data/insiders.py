"""Insider transactions from SEC Form 4.

Every officer, director and 10% owner must file a Form 4 within two business
days of trading their own company's stock. It is free, structured, and filed
under penalty of perjury, which makes it better evidence than almost anything
else this site ingests.

The distinction that matters, and the reason this module exists rather than a
raw count:

    P  open-market purchase   someone chose to buy, with their own money
    S  open-market sale       someone chose to sell
    A  grant or award         the company gave them shares
    M  option exercise        they converted options they already held
    F  shares withheld        the company kept shares to pay their tax bill
    G  gift

Only P and S are decisions. A, M, F and G are compensation mechanics that happen
on a vesting schedule nobody chose the timing of. Most "insider selling" you
read about is F — tax withholding on vesting — and reporting that as a signal is
how the number gets misread. So they are stored, and shown, separately.

Nothing here is advice about what insider activity means. It reports what was
filed.
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable

import requests

from data import settings
from data.edgar import EdgarUnavailable, _ticker_to_cik, _user_agent

log = logging.getLogger(__name__)

# The codes a human chose to make.
DECISIONS = {"P": "buy", "S": "sell"}
# Everything else, kept apart from the signal.
MECHANICS = {"A": "award", "M": "option exercise", "F": "withheld for tax",
             "G": "gift", "C": "conversion", "D": "disposition to issuer"}


def _text(node: ET.Element | None, *path: str) -> str:
    """Form 4 wraps most values in a <value> child, but not always."""
    for step in path:
        if node is None:
            return ""
        node = node.find(step)
    if node is None:
        return ""
    value = node.find("value")
    raw = (value.text if value is not None else node.text) or ""
    return raw.strip()


def _number(node: ET.Element | None, *path: str) -> float | None:
    raw = _text(node, *path)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_form4(xml: str, symbol: str, accession: str) -> list[dict]:
    """Every reportable transaction in one filing. Malformed filings give none."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        log.debug("Form 4 %s did not parse: %s", accession, exc)
        return []

    owner = _text(root.find("reportingOwner"), "reportingOwnerId", "rptOwnerName")
    rel = root.find("reportingOwner/reportingOwnerRelationship")
    roles: list[str] = []
    if rel is not None:
        title = _text(rel, "officerTitle")
        if _text(rel, "isOfficer") in ("1", "true"):
            roles.append(title or "Officer")
        if _text(rel, "isDirector") in ("1", "true"):
            roles.append("Director")
        if _text(rel, "isTenPercentOwner") in ("1", "true"):
            roles.append("10% owner")
    role = ", ".join(roles) or "Insider"

    out: list[dict] = []
    # Derivative transactions are options and similar; the shares are notional
    # until exercised, so only the ordinary share table is read.
    for txn in root.findall(".//nonDerivativeTransaction"):
        code = _text(txn, "transactionCoding", "transactionCode").upper()
        if code not in DECISIONS and code not in MECHANICS:
            continue
        shares = _number(txn, "transactionAmounts", "transactionShares")
        price = _number(txn, "transactionAmounts", "transactionPricePerShare")
        traded = _text(txn, "transactionDate") or _text(root, "periodOfReport")
        if not traded:
            continue
        # A for acquired, D for disposed. Trust this over guessing from the
        # code, because the codes overlap on direction.
        acquired = _text(txn, "transactionAmounts",
                         "transactionAcquiredDisposedCode").upper()
        direction = "buy" if acquired == "A" else "sell"
        out.append({
            "accession": accession, "symbol": symbol, "traded_at": traded,
            "owner": owner or "Undisclosed", "role": role, "code": code,
            "shares": shares, "price": price,
            "value": (shares * price) if (shares and price) else None,
            "direction": direction,
        })
    return out


def fetch(conn: sqlite3.Connection, symbols: Iterable[str], since_days: int = 180,
          max_per_symbol: int = 12, progress=None) -> tuple[int, int]:
    """Read Form 4s filed since `since_days` that we have not read before.

    Returns (filings read, transactions parsed). Both, because it used to
    return only the first: a run that fetched hundreds of filings and parsed
    nothing out of any of them printed a healthy number and published a site
    with no insider data anywhere. A filing already in the cache is never
    fetched again — they do not change once filed.
    """
    symbols = [s.upper() for s in symbols]
    if settings.get("data.provider") == "synthetic":
        return 0

    base = (settings.get("edgar.base_url") or "https://data.sec.gov").rstrip("/")
    session = requests.Session()
    cik_map = _ticker_to_cik(session)          # raises EdgarUnavailable if SEC is down
    cutoff = (dt.date.today() - dt.timedelta(days=since_days)).isoformat()

    seen = {r["accession"] for r in
            conn.execute("SELECT accession FROM insider_filings")}
    added = 0
    parsed = 0
    total = len(symbols)

    for index, symbol in enumerate(symbols, 1):
        if progress and (index % 50 == 0 or index == total):
            progress(index, total, added, parsed)
        cik = cik_map.get(symbol)
        if not cik:
            continue
        try:
            resp = session.get(f"{base}/submissions/{cik}.json",
                               headers={"User-Agent": _user_agent()}, timeout=30)
            time.sleep(0.11)
            if resp.status_code != 200:
                continue
            recent = (resp.json().get("filings") or {}).get("recent") or {}
        except Exception as exc:                   # noqa: BLE001
            log.debug("submissions failed for %s: %s", symbol, exc)
            continue

        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accessions = recent.get("accessionNumber") or []
        primaries = recent.get("primaryDocument") or []
        wanted: list[tuple[str, str, str]] = []
        for form, filed, accession, primary in zip(forms, dates, accessions, primaries):
            if form != "4" or filed < cutoff or accession in seen:
                continue
            wanted.append((filed, accession, primary))
            if len(wanted) >= max_per_symbol:
                break

        for filed, accession, primary in wanted:
            rows = _read_filing(session, cik, accession, primary, symbol)
            _store(conn, accession, symbol, filed, rows)
            seen.add(accession)
            added += 1
            parsed += len(rows)
    conn.commit()
    return added, parsed


def raw_document(primary: str) -> str:
    """The machine-readable Form 4, not the page SEC renders for humans.

    `primaryDocument` in the submissions feed usually points at an XSL
    rendering — `xslF345X03/doc4.xml` — which despite the .xml suffix serves
    HTML. Fetching that returned 200, the XML parser rejected it, the filing
    was recorded as read, and the transaction table stayed empty. Every stock
    page on the site showed no insider activity while the nightly reported
    filings read.

    The raw document is the same name one directory up.
    """
    return primary.split("/")[-1] if "/" in primary else primary


def _read_filing(session, cik: str, accession: str, primary: str,
                 symbol: str) -> list[dict]:
    stripped = accession.replace("-", "")
    number = cik[3:].lstrip("0") if cik.startswith("CIK") else cik.lstrip("0")
    url = (f"https://www.sec.gov/Archives/edgar/data/{number}/"
           f"{stripped}/{raw_document(primary)}")
    try:
        resp = session.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
        time.sleep(0.11)
        if resp.status_code != 200:
            return []
        return parse_form4(resp.text, symbol, accession)
    except Exception as exc:                       # noqa: BLE001
        log.debug("Form 4 %s unreadable: %s", accession, exc)
        return []


def _store(conn: sqlite3.Connection, accession: str, symbol: str, filed: str,
           rows: list[dict]) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT OR REPLACE INTO insider_filings"
        "(accession, symbol, filed_at, fetched_at, parsed) VALUES (?,?,?,?,1)",
        (accession, symbol, filed, now))
    for row in rows:
        conn.execute(
            "INSERT OR REPLACE INTO insider_transactions"
            "(accession, symbol, traded_at, owner, role, code, shares, price,"
            " value, direction) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["accession"], row["symbol"], row["traded_at"], row["owner"],
             row["role"], row["code"], row["shares"], row["price"], row["value"],
             row["direction"]))


def summary(conn: sqlite3.Connection, symbols: Iterable[str],
            window_days: int = 180) -> dict[str, dict]:
    """Per symbol: the open-market decisions, and the mechanics, kept apart."""
    cutoff = (dt.date.today() - dt.timedelta(days=window_days)).isoformat()
    wanted = {s.upper() for s in symbols}
    out: dict[str, dict] = {}
    rows = conn.execute(
        "SELECT * FROM insider_transactions WHERE traded_at >= ? ORDER BY traded_at DESC",
        (cutoff,))
    for row in rows:
        symbol = row["symbol"]
        if symbol not in wanted:
            continue
        entry = out.setdefault(symbol, {
            "symbol": symbol, "window_days": window_days,
            "buys": 0, "sells": 0, "buy_value": 0.0, "sell_value": 0.0,
            "buyers": [], "sellers": [], "mechanics": 0, "recent": [],
        })
        code = row["code"]
        if code in DECISIONS:
            side = "buys" if row["direction"] == "buy" else "sells"
            entry[side] += 1
            entry[f"{row['direction']}_value"] += float(row["value"] or 0.0)
            names = entry["buyers"] if row["direction"] == "buy" else entry["sellers"]
            if row["owner"] not in names:
                names.append(row["owner"])
        else:
            entry["mechanics"] += 1
        if len(entry["recent"]) < 8:
            entry["recent"].append({
                "traded_at": row["traded_at"], "owner": row["owner"],
                "role": row["role"], "code": code,
                "what": DECISIONS.get(code) or MECHANICS.get(code, code),
                "decision": code in DECISIONS,
                "shares": row["shares"], "price": row["price"],
                "value": row["value"], "direction": row["direction"],
            })
    for entry in out.values():
        entry["buy_value"] = round(entry["buy_value"], 2)
        entry["sell_value"] = round(entry["sell_value"], 2)
    return out
