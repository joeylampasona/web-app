"""Offline: trades by members of the House, read from the Clerk's reports.

No network and no PDFs: the fixtures are the text a report gives up, in the
shapes the real ones were seen in on 2026-11-26.

    python tools/test_congress.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from data import congress, store                  # noqa: E402
from publish import health                        # noqa: E402

FAILED: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:<70} {got!r}"
          + ("" if ok else f"   want {want!r}"))
    if not ok:
        FAILED.append(label)


HEAD = """P\x00\x00\x00\x00\x00\x00\x00 T\x00\x00\x00\x00\x00\x00 R\x00\x00\x00\x00\x00
Clerk of the House of Representatives • Legislative Resource Center
F\x00\x00\x00\x00 I\x00\x00\x00\x00\x00\x00
Name: Hon. Pat Example
Status: Member
State/District:NJ07
T\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
ID Owner Asset Transaction
Type
Date Notification
Date
Amount Cap.
Gains >
$200?
"""
TAIL = """* For the complete list of asset type abbreviations, please visit https://fd.house.gov/.
I\x00\x00\x00 V\x00\x00\x00 D\x00\x00\x00
State Street Bank & Trust Co.
L\x00\x00\x00: US
I\x00\x00 P\x00\x00 O\x00\x00
Yes No
C\x00\x00 S\x00\x00
I CERTIFY that the statements I have made are true.
Digitally Signed: Hon. Pat Example, 11/19/2026
Filing ID #20036844
"""
LONG = ("D\x00\x00: Sold on the instruction of an independent adviser who manages the "
        "account without any direction from the filer or the filer's spouse at all")

BODY = f"""Johnson & Johnson Common Stock
(JNJ) [ST]
S (partial) 10/27/202611/12/2026 $1,001 - $15,000
F\x00\x00 S\x00\x00: New
S\x00\x00 O\x00: State Street Bank & Trust Co.
Microsoft Corporation - Common
Stock (MSFT) [ST]
P 10/27/202611/12/2026 $15,001 -
$50,000
F\x00\x00 S\x00\x00: New
U.S. Treasury Note [GS] P 10/20/202611/05/2026 $50,001 -
$100,000
F\x00\x00 S\x00\x00: New
D\x00\x00: 3.875%, 06/15/2028
SP Berkshire Hathaway Inc. New
(BRK/B) [ST]
S 10/07/202610/22/2026$1,001 - $15,000
Filing ID #20036844
ID Owner Asset Transaction
Type
Date Notification
Date
Amount Cap.
Gains >
$200?
F\x00\x00 S\x00\x00: Amended
S\x00\x00 O\x00: State Street Bank & Trust Co. SP
JT NVIDIA Corporation - Common Stock
(NVDA) [OP]
P 10/08/202610/09/2026 $1,001 - $15,000
F\x00\x00 S\x00\x00: New
{LONG}
Apple Inc. - Common Stock (AAPL)
[ST]
E 11/16/202611/21/2026 Over $50,000,000
F\x00\x00 S\x00\x00: New
DC Private Fund LP [HN]
P 11/02/202611/03/2026$250,001 -
$500,000
F\x00\x00 S\x00\x00: New
"""

print("One report's text:")
rows, misses = congress.parse(HEAD + BODY + TAIL)
by = {(r["ticker"] or r["asset"], r["kind"]): r for r in rows}
check("every row on the form is read, and nothing is left unread",
      (len(rows), misses), (7, []))
jnj = by[("JNJ", "ST")]
check("a partial sale, with the two dates the form runs together",
      (jnj["type"], jnj["traded"], jnj["notified"]),
      ("partial sale", "2026-10-27", "2026-11-12"))
check("the amount is the form's band", (jnj["amount_low"], jnj["amount_high"],
                                        jnj["amount_text"]), (1001, 15000, "$1,001 - $15,000"))
msft = by[("MSFT", "ST")]
check("an asset name and a band each broken over two lines",
      (msft["asset"], msft["type"], msft["amount_low"], msft["amount_high"]),
      ("Microsoft Corporation - Common Stock", "buy", 15001, 50000))
note = by[("U.S. Treasury Note", "GS")]
check("a row that is not a stock is kept with its type and no ticker",
      (note["ticker"], note["kind"], note["amount_text"]), (None, "GS", "$50,001 - $100,000"))
brk = by[("BRK.B", "ST")]
check("a share class takes the site's dot, however the filer wrote it", brk["ticker"], "BRK.B")
check("an owner code in front of the asset is whose account it was", brk["owner"], "spouse")
check("a page break and its repeated heading do not come between a row and its details",
      (brk["amended"], brk["amount_text"]), (True, "$1,001 - $15,000"))
option = by[("NVDA", "OP")]
check("an option on a stock is an option: its own type, a joint account",
      (option["kind"], option["owner"], option["type"]), ("OP", "joint", "buy"))
aapl = by[("AAPL", "ST")]
check("no owner code after a short detail line: the member's own", msft["owner"], "self")
check("after a detail long enough to have run on, the owner is not guessed",
      aapl["owner"], None)
check("an exchange, and a band with no top",
      (aapl["type"], aapl["amount_low"], aapl["amount_high"], aapl["amount_text"]),
      ("exchange", 50000000, None, "Over $50,000,000"))
check("a child's account", by[("Private Fund LP", "HN")]["owner"], "child")
check("a scanned paper report has no text and gives nothing, quietly",
      congress.parse(""), ([], []))
check("so does a page that is not a report", congress.parse("Access denied\nTry later"),
      ([], []))
broken = HEAD + "Acme Corp (ACME) [ST]\nP 10/27/2026 10/28/2026 fifteen thousand\n" + TAIL
check("a row whose amount does not read is reported, not dropped in silence",
      (congress.parse(broken)[0], len(congress.parse(broken)[1])), ([], 1))
check("bands, read apart from a report",
      (congress.amount_band("$1,001 -  $15,000"), congress.amount_band("$50,000,001 +"),
       congress.amount_band("$15,001")),
      ((1001, 15000, "$1,001 - $15,000"), (50000001, None, "$50,000,001 +"),
       (15001, 15001, "$15,001")))

# -------------------------------------------------------------- the index
print("\nThe year's index:")
INDEX = ("Prefix\tLast\tFirst\tSuffix\tFilingType\tStateDst\tYear\tFilingDate\tDocID\n"
         "Hon.\tExample\tPat\t\tP\tNJ07\t2026\t11/19/2026\t20036844\n"
         "Hon.\tKean\tThomas H.\tJr\tP\tNJ07\t2026\t10/2/2026\t20030001\n"
         "Hon.\tExample\tPat\t\tO\tNJ07\t2026\t5/15/2026\t10050000\n"
         "Hon.\tPaper\tFiler\t\tP\tTN03\t2026\t11/10/2026\t9116403\n"
         "\tBad\tDate\t\tP\tXX00\t2026\tsoon\t20039999\n")
listed = congress.parse_index(INDEX, 2026)
check("only the periodic transaction reports, with a date that reads",
      [f["doc_id"] for f in listed], ["20036844", "20030001", "9116403"])
check("the member as the index names them", (listed[1]["member"], listed[1]["district"],
                                             listed[1]["filed"]),
      ("Thomas H. Kean Jr", "NJ07", "2026-10-02"))
check("where a report lives", congress.url_of(2026, "20036844"),
      "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20036844.pdf")

# ---------------------------------------------------------------- a night
print("\nA night's reading:")
conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
store.migrate(conn)
conn.execute("CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT)")
TODAY = dt.date(2026, 11, 25)
check("before anything is read the site is told nothing, not 'none'",
      congress.load(conn, {"JNJ"}, TODAY), None)

many = [{"doc_id": str(20000000 + n), "year": 2026, "member": f"Member {n}",
         "district": "ZZ01", "filed": (TODAY - dt.timedelta(days=n)).isoformat()}
        for n in range(30)]
many.append({"doc_id": "19000000", "year": 2025, "member": "Too Old",
             "district": "ZZ02", "filed": "2025-06-01"})
asked: list[str] = []
answers = {"20000001": ("no_text", [], []), "20000003": ("missing", [], [])}


def fake_read(filing):
    asked.append(filing["doc_id"])
    return answers.get(filing["doc_id"], ("read", congress.parse(HEAD + BODY + TAIL)[0], []))


congress.fetch_index = lambda year: [f for f in many if f["year"] == year]
congress.read_filing = fake_read
clock = {"now": 0.0}


def tick(seconds):
    clock["now"] += seconds


said: list[str] = []
got = congress.refresh(conn, TODAY, limit=5, notice=said.append, sleep=tick,
                       clock=lambda: clock["now"])
check("the newest first, no more than the night's cap",
      (asked, got["asked"], got["waiting"]),
      (["20000000", "20000001", "20000002", "20000003", "20000004"], 5, 25))
check("a report filed before the window is not asked for", "19000000" in asked, False)
check("a scanned one and a missing one are counted, and written off",
      (got["read"], got["no_text"], got["transactions"]), (3, 2, 21))
asked.clear()
congress.refresh(conn, TODAY, limit=5, sleep=tick, clock=lambda: clock["now"])
check("the next night carries on where this one stopped, and repeats nothing",
      asked, ["20000005", "20000006", "20000007", "20000008", "20000009"])
before = conn.execute("SELECT COUNT(*) FROM congress_trades").fetchone()[0]
congress.store_filing(conn, many[0], "read", congress.parse(HEAD + BODY + TAIL)[0])
check("a report read twice replaces its rows and never doubles them",
      conn.execute("SELECT COUNT(*) FROM congress_trades").fetchone()[0], before)

asked.clear()
congress.refresh(conn, TODAY, limit=50, budget_seconds=1.0, sleep=tick,
                 clock=lambda: clock["now"])
check("the clock stops a night as well as the cap",
      len(asked), int(1.0 / congress.PAUSE) + 1)

asked.clear()
congress.read_filing = lambda filing: (asked.append(filing["doc_id"]) or ("failed", [], []))
got = congress.refresh(conn, TODAY, limit=50, sleep=tick, clock=lambda: clock["now"],
                       budget_seconds=1e9)
check("a Clerk that stops answering is left alone after a few",
      (len(asked), got["status"]), (congress.FAILURES_BEFORE_STANDING_DOWN, "partial"))
check("and a report that did not answer is asked for again another night",
      conn.execute("SELECT COUNT(*) FROM congress_filings WHERE doc_id = ?",
                   (asked[0],)).fetchone()[0], 0)
congress.fetch_index = lambda year: None
got = congress.refresh(conn, TODAY, notice=said.append)
check("no index at all is said to be down", got["status"], "down")
congress.record(conn, TODAY, got)
row = {r["key"]: r for r in health.report(conn, TODAY)}["congress"]
check("and the source report says so in its own row",
      (row["status"], row["label"], row["from"]),
      ("down", "Congressional trades", "House Clerk"))

# ------------------------------------------------------------ what is shown
print("\nWhat the site is given:")
loaded = congress.load(conn, {"JNJ", "MSFT", "BRK.B", "AAPL"}, TODAY)
check("stocks with a ticker, for names in the universe only",
      sorted(loaded["by_symbol"]), ["AAPL", "BRK.B", "JNJ", "MSFT"])
check("an option, a Treasury note and a private fund are not published",
      "NVDA" in congress.load(conn, {"NVDA", "JNJ"}, TODAY)["by_symbol"], False)
first = loaded["by_symbol"]["JNJ"][0]
check("a published row: who, what, when, the band, and the report itself",
      sorted(first), ["amount", "amount_high", "amount_low", "district", "filed", "member",
                      "notified", "owner", "traded", "type", "url"])
check("the same trade in every report read: one line a member, newest report first",
      (len(loaded["by_symbol"]["JNJ"]), first["member"], first["url"][-12:]),
      (11, "Member 0", "20000000.pdf"))
again = dict(many[0], doc_id="20009999", filed="2026-11-26")
congress.store_filing(conn, again, "read", congress.parse(HEAD + BODY + TAIL)[0])
loaded = congress.load(conn, {"JNJ"}, TODAY)
check("an amended report restating a trade does not make it two",
      (len(loaded["by_symbol"]["JNJ"]), loaded["by_symbol"]["JNJ"][0]["filed"]),
      (11, "2026-11-26"))
check("how much has been read, and how much could not be",
      (loaded["filings_read"], loaded["filings_unread"], loaded["newest_filed"]),
      (12, 2, "2026-11-26"))
recent = congress.recent(loaded, TODAY, days=5)
check("the market page's table: filed in the last few days, newest filing first",
      ([r["filed"] for r in recent][:2], all(r["symbol"] == "JNJ" for r in recent),
       len(recent)), (["2026-11-26", "2026-11-23"], True, 4))
check("a year on, a trade drops off the page",
      congress.load(conn, {"JNJ"}, dt.date(2027, 11, 30))["by_symbol"], {})
check("nothing read yet, nothing recent", congress.recent(None, TODAY), [])

print()
if FAILED:
    print(f"{len(FAILED)} CHECK(S) FAILED: {FAILED}")
    sys.exit(1)
print("ALL CONGRESS CHECKS PASS")
