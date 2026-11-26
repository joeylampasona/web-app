"""Trades by members of the House, from the Clerk's own filings.

A member of Congress who buys or sells a security files a periodic
transaction report within 45 days. The Clerk of the House publishes each
year's filings as an index (one zip, one line a filing) and each report as
a PDF. This reads the index, fetches the reports not yet read, and pulls
the transactions out of their text.

HOUSE ONLY. The Senate publishes the same reports behind a click-through
session with no file to fetch, and the two community feeds that used to
republish both chambers as JSON are gone (403 from the nightly's runner on
2026-11-26). Finnhub's endpoint is a paid one. So senators are not covered
and the page says so.

What a row is and is not:
  * Filed up to 45 days after the trade, and often later. `filed` and
    `traded` are both kept so a page can show the gap.
  * The amount is a band the form offers ($1,001 - $15,000), never a figure.
  * `owner` is whose account it was when the form's owner column can be
    read off the text reliably: "self", "spouse", "joint", "child". None
    when it cannot. A guess here would put a spouse's trade in a member's
    name.
  * A report filed on paper is a scanned image with no text. It is counted
    as unread and not fetched again; nothing is invented for it.

The statute that makes these reports public, 5 U.S.C. 13107, forbids
obtaining or using them for any commercial purpose other than by news and
communications media for dissemination to the general public. What this
module feeds is published free to every reader. See DECISIONS.md.
"""
from __future__ import annotations

import collections
import datetime as dt
import io
import logging
import re
import time
import zipfile

import requests

log = logging.getLogger(__name__)

BASE = "https://disclosures-clerk.house.gov/public_disc"
AGENT = "tape-research"
TIMEOUT = 60

#: New filings read a night, and the clock that stops it sooner. A filing is
#: one small PDF; the first three nights backfill the year (about five
#: hundred reports) and after that a night has a handful.
# Measured from the nightly's runner: sixty reports in 32 seconds.
FILINGS_A_NIGHT = 200
TIME_BUDGET_SECONDS = 110.0
PAUSE = 0.4

#: Failures in a row before the rest of the night's filings are left alone.
FAILURES_BEFORE_STANDING_DOWN = 4

#: How far back filings are read and published, in days.
WINDOW_DAYS = 370
PUBLISHED_DAYS = 365
RECENT_DAYS = 60

OWNERS = {"SP": "spouse", "JT": "joint", "DC": "child"}
TYPES = {"P": "buy", "S": "sell", "S (partial)": "partial sale", "E": "exchange"}

#: What happened to every request made in this process.
OUTCOMES: "collections.Counter[str]" = collections.Counter()

# The last cell of the table's header. The rows follow it.
_HEADER_END = "$200?"
_HEADER_LINES = {"ID Owner Asset Transaction", "Type", "Date Notification", "Date",
                 "Amount Cap.", "Gains >", _HEADER_END,
                 "ID Owner Asset Transaction Type Date Notification Date Amount Cap. "
                 "Gains > $200?"}

# A detail line under a transaction. The form sets its labels in small
# capitals, which arrive as a capital followed by NULs: "FILING STATUS:"
# becomes "F S:", "SUBHOLDING OF:" "S O:", "DESCRIPTION:" "D:".
_DETAIL = re.compile(r"^(?P<label>[A-Z](?: [A-Z]){0,3}):\s*(?P<value>.*)$")
# Details that are free text, and the length past which one may have run on
# to a second line. A line that long leaves it unknown where the next asset
# begins, and with it whether that asset has an owner code in front of it.
# On sixty real reports a line of 96 characters had not broken and one of
# 104 had, so a line is suspected from a little under that.
_FREE_TEXT = {"D", "C"}
RUN_ON_FROM = 90
_RUN_ON = "~"

_AMOUNT = (r"(?:Over\s+\$[\d,]+|\$[\d,]+\s*-\s*\$[\d,]+|\$[\d,]+\s*\+|\$[\d,]+)")
# The cells of a row come out run together as often as not:
# "S 10/07/202610/22/2026$1,001 - $15,000". Nothing between the two dates
# or before the amount can be relied on.
_TRANSACTION = re.compile(
    r"\[(?P<kind>[A-Z0-9]{2})\]\s*"
    r"(?P<type>S \(partial\)|P|S|E)\s+"
    r"(?P<traded>\d{1,2}/\d{1,2}/\d{4})\s*"
    r"(?P<notified>\d{1,2}/\d{1,2}/\d{4})\s*"
    rf"(?P<amount>{_AMOUNT})")
# One row in sixty real reports came out the other way round: the asset's
# first line, then the transaction cells, then the rest of the asset with
# its ticker and type code ("Norwegian Cruise Line HoldingsP 10/20/2026
# 11/09/2026$1,001 - $15,000 Ltd. Ordinary Shares (NCLH) [ST]"). It is told
# from an ordinary row by what follows the amount: more asset and a type
# code, with no detail line in between.
_INTERLEAVED = re.compile(
    r"(?P<type>S \(partial\)|P|S|E)\s+"
    r"(?P<traded>\d{1,2}/\d{1,2}/\d{4})\s*"
    r"(?P<notified>\d{1,2}/\d{1,2}/\d{4})\s*"
    rf"(?P<amount>{_AMOUNT})\s+"
    r"(?P<tail>[^\u00a6\[\]]{1,140}?)\s*\[(?P<kind>[A-Z0-9]{2})\]")
_TICKER = re.compile(r"\(([A-Z][A-Z0-9./\-]{0,7})\)\s*$")
_DATE_PAIR = re.compile(r"\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}/\d{1,2}/\d{4}")
_MARK = "¦"


def spelling(ticker: str) -> str:
    """The site's spelling of a ticker as a filing writes it: a share class
    takes a dot, however the filer punctuated it. BRK/B and BRK-B are BRK.B."""
    return re.sub(r"[/\-]", ".", (ticker or "").strip().upper())


def _iso(text: str) -> str | None:
    try:
        month, day, year = (int(part) for part in text.split("/"))
        return dt.date(year, month, day).isoformat()
    except (ValueError, TypeError):
        return None


def amount_band(text: str) -> tuple[int | None, int | None, str]:
    """(low, high, the band as the form states it). "Over $50,000,000" has
    no top; a single figure is both ends."""
    tidy = re.sub(r"\s+", " ", (text or "").strip())
    figures = [int(f.replace(",", "")) for f in re.findall(r"\$([\d,]+)", tidy)]
    if not figures:
        return None, None, tidy
    if tidy.lower().startswith("over") or tidy.endswith("+"):
        return figures[0], None, tidy
    if len(figures) == 1:
        return figures[0], figures[0], tidy
    return figures[0], figures[1], re.sub(r"\s*-\s*", " - ", tidy)


def lines_of(text: str) -> list[str]:
    """The filing's text as clean lines: NULs out, blanks out."""
    out = []
    for raw in (text or "").replace("\x00", "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            out.append(line)
    return out


def parse(text: str) -> tuple[list[dict], list[str]]:
    """The transactions in one filing's text, and what looked like one and
    did not parse. ([], []) for a filing with no text at all.

    The table's cells come out of the PDF a cell at a time: the asset, which
    can run over lines, ending in its ticker and a type code in brackets;
    then the transaction type, the two dates and the amount band, which can
    also break. Under each row sit detail lines. So the rows are read off
    one stream with the detail lines lifted out and marked, not line by line.
    """
    lines = lines_of(text)
    start = next((i for i, line in enumerate(lines) if line.endswith(_HEADER_END)), None)
    if start is None:
        return [], []
    body = []
    for line in lines[start + 1:]:
        if line.startswith("* For the complete list") or line.startswith("I V D") \
                or line.startswith("I P O") or line.startswith("C S"):
            break
        if line in _HEADER_LINES or re.fullmatch(r"Filing ID #\d+", line):
            continue
        body.append(line)

    # One stream. A detail line becomes a mark carrying its label and value,
    # so what lies between two transactions can be told apart: the details
    # of the one before, and the asset of the one after.
    parts = []
    for line in body:
        detail = _DETAIL.match(line)
        if detail:
            label = detail["label"].replace(" ", "")
            if label in _FREE_TEXT and len(line) >= RUN_ON_FROM:
                label += _RUN_ON
            parts.append(f"{_MARK}{label}={detail['value']}{_MARK}")
        else:
            parts.append(line)
    stream = " ".join(parts)

    rows: list[dict] = []
    found = list(_TRANSACTION.finditer(stream))
    taken = [(m.start(), m.end()) for m in found]
    for odd in _INTERLEAVED.finditer(stream):
        if not any(a < odd.end() and odd.start() < b for a, b in taken):
            found.append(odd)
    found.sort(key=lambda m: m.start())
    previous_end = 0
    for index, match in enumerate(found):
        before = stream[previous_end:match.start()]
        tail = match.groupdict().get("tail")
        # The asset is what follows the last detail mark of the row before.
        cut = before.rfind(_MARK)
        asset_text = before[cut + 1:].strip() if cut >= 0 else before.strip()
        if tail is not None:
            # The asset in two halves, either side of the transaction cells.
            asset_text = f"{asset_text} {tail.strip()}"
        last_label = None
        marks = re.findall(rf"{_MARK}([A-Z]+{_RUN_ON}?)=", before)
        if marks:
            last_label = marks[-1]
        owner = None
        code = re.match(r"^(SP|JT|DC)\s+(?=\S)", asset_text)
        if code:
            owner = OWNERS[code[1]]
            asset_text = asset_text[code.end():]
        elif not (last_label or "").endswith(_RUN_ON):
            # Nothing that could have run on came before it, so the first
            # word of the asset is where an owner code would be, and there
            # is none: the member's own.
            owner = "self"
        ticker = None
        hit = _TICKER.search(asset_text)
        if hit:
            ticker = spelling(hit[1])
            asset_text = asset_text[:hit.start()].strip()
        after = stream[match.end():found[index + 1].start()
                       if index + 1 < len(found) else len(stream)]
        details = dict(re.findall(rf"{_MARK}([A-Z]+){_RUN_ON}?=([^{_MARK}]*){_MARK}", after))
        low, high, band = amount_band(match["amount"])
        rows.append({
            "asset": asset_text[-160:].strip(" -"),
            "ticker": ticker,
            "kind": match["kind"],
            "type": TYPES[match["type"]],
            "traded": _iso(match["traded"]),
            "notified": _iso(match["notified"]),
            "amount_low": low, "amount_high": high, "amount_text": band,
            "owner": owner,
            "amended": (details.get("FS") or "").strip().lower().startswith("amend"),
        })
        previous_end = match.end()

    # What looked like a transaction and was not read: a pair of dates that
    # no row accounts for.
    misses = []
    spans = [(m.start(), m.end()) for m in found]
    for pair in _DATE_PAIR.finditer(stream):
        if not any(a <= pair.start() < b for a, b in spans):
            misses.append(stream[max(0, pair.start() - 90):pair.end() + 40])
    return rows, misses


def text_of(pdf: bytes) -> str:
    """The PDF's text, or "" when it has none (a scanned paper filing) or
    cannot be read."""
    try:
        import pypdf                                  # noqa: PLC0415 - nightly only
        reader = pypdf.PdfReader(io.BytesIO(pdf))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:                          # noqa: BLE001
        log.debug("congress: unreadable PDF: %s", type(exc).__name__)
        return ""


def parse_index(text: str, year: int) -> list[dict]:
    """The periodic transaction reports in a year's index file."""
    lines = (text or "").splitlines()
    if not lines:
        return []
    head = [cell.strip() for cell in lines[0].split("\t")]

    def column(name: str, default: int) -> int:
        return head.index(name) if name in head else default
    last, first, suffix = column("Last", 1), column("First", 2), column("Suffix", 3)
    kind, district = column("FilingType", 4), column("StateDst", 5)
    filed, doc = column("FilingDate", 7), column("DocID", 8)
    out = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.split("\t")]
        if len(cells) <= max(kind, filed, doc) or cells[kind] != "P":
            continue
        filed_on = _iso(cells[filed])
        if not (filed_on and cells[doc].isdigit()):
            continue
        name = " ".join(part for part in (cells[first], cells[last], cells[suffix]) if part)
        out.append({"doc_id": cells[doc], "year": year, "member": name,
                    "district": cells[district], "filed": filed_on})
    return out


def url_of(year: int, doc_id: str) -> str:
    return f"{BASE}/ptr-pdfs/{year}/{doc_id}.pdf"


def _get(url: str) -> requests.Response:
    return requests.get(url, timeout=TIMEOUT,
                        headers={"User-Agent": AGENT, "Accept": "*/*"})


def fetch_index(year: int) -> list[dict] | None:
    """The year's reports, or None when the Clerk did not answer."""
    try:
        response = _get(f"{BASE}/financial-pdfs/{year}FD.zip")
        if response.status_code != 200:
            OUTCOMES[f"index_http_{response.status_code}"] += 1
            return None
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        name = next(n for n in archive.namelist() if n.lower().endswith(".txt"))
        OUTCOMES["index_ok"] += 1
        return parse_index(archive.read(name).decode("utf-8", "replace"), year)
    except (requests.RequestException, zipfile.BadZipFile, StopIteration) as exc:
        OUTCOMES["index_error"] += 1
        log.debug("congress index %s: %s", year, type(exc).__name__)
        return None


def read_filing(filing: dict) -> tuple[str, list[dict], list[str]]:
    """Fetch and parse one report: (status, rows, misses). The status is
    "read", "no_text" for a scanned paper filing, "missing" when the Clerk
    has no such file, or "failed" when it did not answer, which is the only
    one worth asking about again."""
    try:
        response = _get(url_of(filing["year"], filing["doc_id"]))
    except requests.RequestException:
        OUTCOMES["filing_error"] += 1
        return "failed", [], []
    if response.status_code == 404:
        OUTCOMES["filing_missing"] += 1
        return "missing", [], []
    if response.status_code != 200:
        OUTCOMES[f"filing_http_{response.status_code}"] += 1
        return "failed", [], []
    text = text_of(response.content)
    if len(lines_of(text)) < 5:
        OUTCOMES["filing_no_text"] += 1
        return "no_text", [], []
    rows, misses = parse(text)
    OUTCOMES["filing_read"] += 1
    return "read", rows, misses


# ------------------------------------------------------------- storage

def store_filing(conn, filing: dict, status: str, rows: list[dict]) -> None:
    """Keep one report and its transactions. Reading a report twice
    replaces what the first read kept; it never doubles it."""
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    conn.execute("DELETE FROM congress_trades WHERE doc_id = ?", (filing["doc_id"],))
    for seq, row in enumerate(rows):
        conn.execute(
            "INSERT INTO congress_trades(doc_id, seq, member, district, ticker, asset,"
            " kind, type, owner, traded, notified, filed, amount_low, amount_high,"
            " amount_text, amended, year) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (filing["doc_id"], seq, filing["member"], filing["district"],
             row.get("ticker"), row.get("asset") or "", row.get("kind") or "",
             row.get("type") or "", row.get("owner"), row.get("traded"),
             row.get("notified"), filing["filed"], row.get("amount_low"),
             row.get("amount_high"), row.get("amount_text") or "",
             1 if row.get("amended") else 0, filing["year"]))
    conn.execute(
        "INSERT OR REPLACE INTO congress_filings(doc_id, year, member, district,"
        " filed, status, transactions, read_at) VALUES (?,?,?,?,?,?,?,?)",
        (filing["doc_id"], filing["year"], filing["member"], filing["district"],
         filing["filed"], status, len(rows), now))


def known(conn) -> set[str]:
    return {row[0] for row in conn.execute("SELECT doc_id FROM congress_filings")}


def refresh(conn, today: dt.date, *, limit: int = FILINGS_A_NIGHT,
            budget_seconds: float = TIME_BUDGET_SECONDS, notice=None,
            sleep=time.sleep, clock=time.monotonic) -> dict:
    """Read the newest reports not yet read, up to `limit` and the clock.

    Never raises. Returns counts for the source report: {"listed", "waiting",
    "asked", "read", "no_text", "failed", "transactions", "status"}.
    """
    out = {"listed": 0, "waiting": 0, "asked": 0, "read": 0, "no_text": 0,
           "failed": 0, "transactions": 0, "status": "ok"}
    try:
        import pypdf                                  # noqa: F401, PLC0415
    except ImportError:
        # Without the PDF reader every report would look like a scanned one
        # and be written off for good. Read nothing instead.
        out["status"] = "down"
        if notice:
            notice("congress: pypdf is not installed; no reports read tonight.")
        return out
    try:
        return _refresh(conn, today, out, limit, budget_seconds, notice, sleep, clock)
    except Exception as exc:                          # noqa: BLE001 - never the nightly
        conn.rollback()
        out["status"] = "down"
        if notice:
            notice(f"congress: {type(exc).__name__}: {str(exc)[:160]}; nothing kept tonight.")
        return out


def _refresh(conn, today, out, limit, budget_seconds, notice, sleep, clock) -> dict:
    first = today - dt.timedelta(days=WINDOW_DAYS)
    listed: list[dict] = []
    answered = False
    for year in sorted({today.year, first.year}, reverse=True):
        found = fetch_index(year)
        if found is None:
            continue
        answered = True
        listed += [f for f in found if f["filed"] >= first.isoformat()]
    if not answered:
        out["status"] = "down"
        if notice:
            notice("congress: the Clerk's index did not answer; nothing read tonight.")
        return out
    out["listed"] = len(listed)
    seen = known(conn)
    waiting = sorted((f for f in listed if f["doc_id"] not in seen),
                     key=lambda f: (f["filed"], f["doc_id"]), reverse=True)
    out["waiting"] = len(waiting)
    started = clock()
    failed_in_a_row = 0
    for filing in waiting[:limit]:
        if clock() - started > budget_seconds:
            break
        if failed_in_a_row >= FAILURES_BEFORE_STANDING_DOWN:
            out["status"] = "partial"
            if notice:
                notice(f"congress: {failed_in_a_row} filings in a row did not "
                       f"answer; the rest wait for tomorrow.")
            break
        out["asked"] += 1
        status, rows, _ = read_filing(filing)
        if status == "failed":
            failed_in_a_row += 1
            out["failed"] += 1
        else:
            failed_in_a_row = 0
            store_filing(conn, filing, status, rows)
            if status == "read":
                out["read"] += 1
                out["transactions"] += len(rows)
            else:
                out["no_text"] += 1
        sleep(PAUSE)
    conn.commit()
    out["waiting"] -= out["asked"] - out["failed"]
    if notice:
        notice(f"congress: {out['listed']:,} House reports in the window, "
               f"{out['asked']:,} read tonight ({out['read']:,} with text, "
               f"{out['transactions']:,} transactions; {out['no_text']:,} "
               f"scanned or missing; {out['failed']:,} did not answer), "
               f"{out['waiting']:,} still to read.")
    return out


# ------------------------------------------------------------- reading

def ever_fetched(conn) -> bool:
    try:
        return conn.execute("SELECT 1 FROM congress_filings LIMIT 1").fetchone() is not None
    except Exception:                                 # noqa: BLE001 - no table yet
        return False


def _published(row) -> dict:
    return {
        "member": row["member"], "district": row["district"],
        "type": row["type"], "owner": row["owner"],
        "traded": row["traded"], "notified": row["notified"], "filed": row["filed"],
        "amount_low": row["amount_low"], "amount_high": row["amount_high"],
        "amount": row["amount_text"],
        "url": url_of(row["year"], row["doc_id"]),
    }


def load(conn, universe, today: dt.date) -> dict | None:
    """What the site publishes: stock transactions in the universe over the
    last year, by symbol, newest first. None before the first fetch, which
    is a different thing from a year with none.

    An amended report restates the transaction it corrects. The two are
    told apart from two trades only by being identical in every published
    field, and then the newest filing stands.
    """
    if not ever_fetched(conn):
        return None
    names = {str(s).upper() for s in universe}
    since = (today - dt.timedelta(days=PUBLISHED_DAYS)).isoformat()
    by_symbol: dict[str, list[dict]] = {}
    seen: set[tuple] = set()
    for row in conn.execute(
            "SELECT * FROM congress_trades WHERE kind = 'ST' AND ticker IS NOT NULL"
            " AND traded >= ? ORDER BY traded DESC, filed DESC, doc_id DESC, seq", (since,)):
        symbol = row["ticker"]
        if symbol not in names:
            continue
        key = (row["member"], symbol, row["type"], row["traded"], row["amount_low"],
               row["amount_high"], row["owner"])
        if key in seen:
            continue
        seen.add(key)
        by_symbol.setdefault(symbol, []).append(_published(row))
    counts = conn.execute(
        "SELECT SUM(status = 'read'), SUM(status != 'read'), MAX(filed)"
        " FROM congress_filings").fetchone()
    return {"by_symbol": by_symbol,
            "filings_read": int(counts[0] or 0), "filings_unread": int(counts[1] or 0),
            "newest_filed": counts[2]}


def recent(loaded: dict | None, today: dt.date, days: int = RECENT_DAYS) -> list[dict]:
    """The market page's table: every published transaction filed in the
    last `days`, newest filing first, each with its symbol."""
    if not loaded:
        return []
    since = (today - dt.timedelta(days=days)).isoformat()
    rows = [{"symbol": symbol, **row}
            for symbol, held in loaded["by_symbol"].items()
            for row in held if (row["filed"] or "") >= since]
    rows.sort(key=lambda r: (r["filed"], r["traded"] or "", r["symbol"]), reverse=True)
    return rows


# ------------------------------------------------------- the night's row

COPY = {
    "header": "Trades in these stocks by members of the House of Representatives, "
              "from the periodic transaction reports they file with the Clerk.",
    "footer": "Members have up to 45 days to report a trade and some take longer, so "
              "the filed date matters as much as the traded one. Amounts are the bands "
              "the form offers, not figures. Senators are not covered: the Senate "
              "publishes no file to read. Reports filed on paper are scanned images "
              "and are not read. Not a signal.",
}


def record(conn, session: dt.date, got: dict) -> None:
    """Tonight's row in the source report, from what refresh() returned."""
    from publish import health                        # noqa: PLC0415 - avoids a cycle
    if got.get("status") == "down":
        detail = "The Clerk's index did not answer; no reports read tonight."
    elif not got.get("asked"):
        detail = (f"{got.get('listed', 0):,} House reports in the window, "
                  f"all already read.")
    else:
        detail = (f"{got['asked']:,} new House reports asked for: {got['read']:,} "
                  f"read ({got['transactions']:,} transactions), {got['no_text']:,} "
                  f"scanned or missing, {got['failed']:,} did not answer; "
                  f"{got['waiting']:,} still to read.")
    health.record(conn, "congress", session, detail, status=got.get("status") or "ok")
