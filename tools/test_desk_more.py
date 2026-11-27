"""Offline: the Market Desk blocks the ingest used to drop, stale options
reads, and the day's earnings figures from Finnhub.

    python tools/test_desk_more.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from catalysts import finnhub                     # noqa: E402
from data import marketdesk, store                # noqa: E402
from publish import discord, health, writer       # noqa: E402

FAILED: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:<68} {got!r}"
          + ("" if ok else f"   want {want!r}"))
    if not ok:
        FAILED.append(label)


# --------------------------------------------------- the desk's file
PAYLOAD = {
    "schema_version": "1.7", "generated_at_utc": "2026-11-26T08:17:00Z",
    "universe_size": 5000,
    "stage_status": {"filings": "ok", "tape": "ok"},
    "signals": [
        {"ticker": "ADV", "source": "TAPE", "reason": "GAP", "detail": "+7.2%",
         "short_interest": {"settlement": "2026-10-30", "shares": 609044,
                            "chg_pct": 7.95, "days_to_cover": 11.96}},
        {"ticker": "BBB", "source": "TAPE", "reason": "GAP", "detail": "+3%",
         "short_interest": None},
    ],
    "earnings": [],
    "gamma": {"d": "2026-11-18",
              "index": [{"symbol": "SPX", "label": "S&P 500", "net": -9.8e10,
                         "flip": 7581.45, "call_wall": 7700.0, "put_wall": 7000.0,
                         "regime": "negative"}],
              "sectors": [{"symbol": "XLU", "label": "Utilities", "net": 3.2e7}]},
    "squeeze": {"altg": {"short_ratio": 0.58, "short_ratio_20d": 0.466,
                         "short_days": 21, "met": 1,
                         "why": ["short volume 58% vs 47% 20d"], "watch": False}},
    "events_crossing": [{"date": "2026-12-02", "name": "FOMC", "label": "FOMC decision"}],
    "earnings_iv": {"as_of": "2026-11-25",
                    "upcoming": [{"ticker": "DE", "report_date": "2026-11-25",
                                  "d": "2026-11-18", "implied_pct": 7.6}],
                    "settled": [{"ticker": "ADI", "report_date": "2026-11-24",
                                 "d": "2026-11-18", "implied_pct": 9.21}],
                    "tally": {"n": 168}},
}

print("The desk's dropped blocks:")
conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
store.migrate(conn)
marketdesk._config = lambda: ("owner/desk", "token")
marketdesk._fetch_file = lambda repo, token, path: (
    PAYLOAD if path.endswith("2026-11-25.json") else None)
marketdesk.ingest(conn, dt.date(2026, 11, 25))
more = marketdesk.extras(conn)
check("dealer gamma is kept with its own date", more["gamma"]["d"], "2026-11-18")
check("the squeeze read, by ticker in capitals", list(more["squeeze"]), ["ALTG"])
check("short interest only for the names that carry one",
      {k: v["days_to_cover"] for k, v in more["short_interest"].items()}, {"ADV": 11.96})
check("macro releases inside the hold", more["events_crossing"][0]["name"], "FOMC")
check("the newest night the desk read option chains",
      marketdesk.options_read_on(conn), "2026-11-18")

# A later run with no gamma and no squeeze: gamma is carried, squeeze is not.
later = {**PAYLOAD, "gamma": None, "squeeze": {}, "events_crossing": [],
         "signals": [], "earnings_iv": None}
marketdesk._fetch_file = lambda repo, token, path: (
    later if path.endswith("2026-11-26.json") else None)
marketdesk.ingest(conn, dt.date(2026, 11, 26))
more = marketdesk.extras(conn)
check("a night without gamma keeps the last one, dated",
      (more["gamma"] or {}).get("d"), "2026-11-18")
check("a night without a squeeze read has none: it is about that night",
      more["squeeze"], {})

# Desk schema 1.8: the options read and short volume, per name.
conn.execute("INSERT INTO universe(symbol, as_of, price, passed) VALUES"
             " ('ZS', '2026-11-27', 230.0, 1), ('NVDA', '2026-11-27', 149.0, 1)")
newer = {**PAYLOAD, "schema_version": "1.8", "signals": [], "gamma": None,
         "options_read": {"d": "2026-11-27", "by_ticker": {
             "ZS": {"iv30": 61.6, "iv_rank": None, "exp_move_pct": 12.5},
             "NOTOURS": {"iv30": 40.0}}},
         "short_volume": {"d": "2026-11-25", "by_ticker": {
             "NVDA": [0.381, 0.313, 21], "NOTOURS": [0.5, 0.5, 21]}}}
marketdesk._fetch_file = lambda repo, token, path: (
    newer if path.endswith("2026-11-27.json") else None)
marketdesk.ingest(conn, dt.date(2026, 11, 27))
more = marketdesk.extras(conn)
check("the options read is kept for the site's own names only",
      (more["options_read"]["d"], sorted(more["options_read"]["by_ticker"])),
      ("2026-11-27", ["ZS"]))
check("and so is the day's short volume",
      more["short_volume"]["by_ticker"], {"NVDA": [0.381, 0.313, 21]})
check("a fresh options read moves the date the desk's reads are judged by",
      marketdesk.options_read_on(conn), "2026-11-27")
# Desk schema 1.9: the brief's sentence per name, and the gap fade watch.
nineteen = {**newer, "schema_version": "1.9",
            "stories": {"zs": "3 insiders bought $11.4M in 30 days,\n the latest $268K.",
                        "NOTOURS": "Not a name the site follows.",
                        "NVDA": None, "LONG": "x" * 400},
            "gap_fade": {"d": "2026-11-28", "floor": 20000000.0,
                         "up": [{"ticker": "zs", "gap": 6.1, "dollar_vol": 4.1e8},
                                {"ticker": "NOTOURS", "gap": 5.0, "dollar_vol": 2.2e7},
                                {"ticker": "BAD", "gap": "n/a"}],
                         "down": [],
                         "n_up": 11, "n_down": 0,
                         "record": {"up": {"h3": {"n": 140, "x": -0.42, "nights": 61,
                                                  "t": -2.1, "neg": 58.0, "thin": False},
                                           "h20": None}}}}
conn.execute("INSERT INTO universe(symbol, as_of, price, passed) VALUES"
             " ('LONG', '2026-11-27', 10.0, 1)")
marketdesk._fetch_file = lambda repo, token, path: (
    nineteen if path.endswith("2026-11-28.json") else None)
marketdesk.ingest(conn, dt.date(2026, 11, 28))
more = marketdesk.extras(conn)
check("a 1.9 file is accepted", conn.execute(
    "SELECT schema_version FROM desk_runs WHERE as_of = '2026-11-28'").fetchone()[0], "1.9")
check("stories: the site's names only, upper-cased, one line",
      {k: v for k, v in more["stories"].items() if k != "LONG"},
      {"ZS": "3 insiders bought $11.4M in 30 days, the latest $268K."})
check("a story past the contract's one line is cut, not run on",
      (len(more["stories"]["LONG"]), more["stories"]["LONG"][-1]), (marketdesk.STORY_MAX, "…"))
fade = more["gap_fade"]
check("the fade watch keeps names the site does not follow, drops bad rows",
      [r["ticker"] for r in fade["up"]], ["ZS", "NOTOURS"])
check("its counts, its floor and its record pass through",
      (fade["n_up"], fade["n_down"], fade["floor"], fade["record"]["up"]["h3"]["x"]),
      (11, 0, 20000000.0, -0.42))
check("a count smaller than the rows shown is not believed",
      marketdesk._gap_fade({"d": "x", "up": [{"ticker": "A", "gap": 1}], "n_up": 0})["n_up"], 1)
check("no gap fade without a date or rows",
      (marketdesk._gap_fade({"up": [{"ticker": "A", "gap": 1}]}),
       marketdesk._gap_fade({"d": "x", "up": [], "down": []})), (None, None))
check("a 1.8 file has no stories and no fade watch, not an error",
      (marketdesk._stories(None, None), marketdesk._extras(newer, [])["gap_fade"]), ({}, None))

for n in range(1, 7):
    day = dt.date(2026, 11, 27) + dt.timedelta(days=n)
    marketdesk._fetch_file = lambda repo, token, path, day=day: (
        newer if path.endswith(f"{day}.json") else None)
    marketdesk.ingest(conn, day)
kept = [r[0] for r in conn.execute(
    "SELECT as_of FROM desk_runs WHERE extras != 'null' ORDER BY as_of")]
check("only the newest few runs keep a market's worth of short volume",
      (len(kept), kept[0]), (marketdesk.EXTRAS_KEPT, "2026-11-29"))
check("a later run without stories has none: they are about that night",
      marketdesk.extras(conn)["stories"], {})

# A database from before the column existed still answers.
bare = sqlite3.connect(":memory:")
bare.row_factory = sqlite3.Row
check("no desk table at all: empty, not an error",
      marketdesk.extras(bare)["squeeze"], {})

# ------------------------------------------------ judging the reads
print("\nThe desk's options reads, judged by their own date:")
conn.execute("CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT)")
for day in ("2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24",
            "2026-11-25"):
    conn.execute("INSERT INTO bars(symbol, date, open, high, low, close, volume)"
                 " VALUES ('AAA', ?, 1, 1, 1, 1, 1)", (day,))
conn.commit()
session = dt.date(2026, 11, 25)
run = {"as_of": "2026-11-25", "stage_status": {"tape": "ok"},
       "options_read_on": "2026-11-18"}
rows = {r["key"]: r for r in health.report(conn, session, run)}
check("every stage ok and the run current: the desk row is ok", rows["desk"]["status"], "ok")
check("but its options reads are five sessions old, and said to be",
      (rows["desk_options"]["status"], "five sessions" in rows["desk_options"]["detail"]),
      ("behind", True))
fresh = {**run, "options_read_on": "2026-11-24"}
check("a read one session behind the run is ordinary",
      {r["key"]: r for r in health.report(conn, session, fresh)}["desk_options"]["status"],
      "ok")
check("a desk that sends no options reads has no row for them",
      "desk_options" in {r["key"] for r in health.report(
          conn, session, {"as_of": "2026-11-25", "stage_status": {}})}, False)

print("\nA priced move, and how old its read is:")
check("read the night before the edition", writer._read_is_stale("2026-11-24", session), False)
check("read on Friday for a Monday edition",
      writer._read_is_stale("2026-11-20", dt.date(2026, 11, 23)), False)
check("read a week before", writer._read_is_stale("2026-11-18", session), True)
check("no date to judge by is not called stale", writer._read_is_stale(None, session), False)
event = {"ticker": "DE", "type": "earnings", "date": "2026-11-25"}
priced = {"DE": {"report_date": "2026-11-25", "implied_pct": 7.6, "d": "2026-11-18",
                 "stale": True}}
check("the calendar's event carries the read's date and that it is stale",
      {k: v for k, v in writer._with_priced(event, priced).items() if k.startswith("priced")},
      {"priced_move_pct": 7.6, "priced_read_on": "2026-11-18", "priced_stale": True})
check("Discord leaves a stale read out rather than call it what options priced",
      discord.implied_moves({"priced": {"upcoming": [
          {"ticker": "DE", "implied_pct": 7.6, "stale": True},
          {"ticker": "ZS", "implied_pct": 11.2, "stale": False}]}}), {"ZS": 11.2})

# ------------------------------------------------------------ Finnhub
print("\nFinnhub's calendar:")
DAY = dt.date(2026, 11, 25)
CALENDAR = {"earningsCalendar": [
    {"date": "2026-11-25", "symbol": "DE", "hour": "bmo", "epsActual": 4.12,
     "epsEstimate": 3.9, "revenueActual": 10_580_000_000, "revenueEstimate": 10_300_000_000},
    {"date": "2026-11-25", "symbol": "ZS", "hour": "amc", "epsActual": None,
     "epsEstimate": 0.85, "revenueActual": 0, "revenueEstimate": 812_000_000},
    {"date": "2026-11-25", "symbol": "NOHR", "hour": "", "epsActual": 0.1,
     "epsEstimate": 0.0},
    {"date": "2026-11-26", "symbol": "LATER", "hour": "bmo"},
    {"date": "2026-11-25", "symbol": "J", "hour": "bmo", "epsActual": 2.2,
     "epsEstimate": 2.1671, "revenueActual": 4_712_280_000,
     "revenueEstimate": 2_606_261_955},
]}
found = finnhub.parse(CALENDAR, DAY)
check("only the day asked about", sorted(found), ["DE", "J", "NOHR", "ZS"])
check("a revenue 81% over its estimate is two definitions, not a beat",
      (found["J"]["revenue"], found["J"]["revenue_estimate"],
       found["J"]["revenue_surprise_pct"]), (4_712_280_000, None, None))
check("before the open, as a time the run can sort by", found["DE"]["hour"], dt.time(7, 0))
check("the surprise, earnings and revenue",
      (found["DE"]["surprise_pct"], found["DE"]["revenue_surprise_pct"]), (5.6, 2.7))
check("a revenue of zero is a row not filled in, not a company with no sales",
      found["ZS"]["revenue"], None)
check("no surprise against an estimate of zero", found["NOHR"]["surprise_pct"], None)
check("enough for a line on its own: a time and a figure",
      (finnhub.complete(found["DE"]), finnhub.complete(found["ZS"]),
       finnhub.complete(found["NOHR"])), (True, False, False))

yahoo = {"hour": dt.time(16, 5), "eps": 0.91, "estimate": 0.86, "surprise_pct": 5.8}
both = finnhub.merged(yahoo, found["ZS"])
check("Finnhub has no figure yet: Yahoo's figure with Yahoo's own estimate",
      (both["eps"], both["estimate"], both["surprise_pct"]), (0.91, 0.86, 5.8))
check("and Finnhub's revenue estimate is not passed off as a result",
      (both["revenue"], both["revenue_estimate"]), (None, 812_000_000))
check("Finnhub alone", finnhub.merged(None, found["DE"])["eps"], 4.12)
check("Yahoo alone, as before there was a key", finnhub.merged(yahoo, None)["eps"], 0.91)
check("neither", finnhub.merged(None, None), None)
check("no time of day from either: no line", finnhub.merged(None, found["NOHR"]), None)

os.environ.pop("FINNHUB_API_KEY", None)
check("without a key nothing is asked", (finnhub.enabled(), finnhub.calendar(DAY)),
      (False, {}))


class Reply:
    status_code = 200

    def json(self):
        return CALENDAR


seen: dict = {}


def fake_get(url, params=None, headers=None, timeout=None):
    seen.update(url=url, params=params, headers=headers)
    return Reply()


finnhub.requests.get = fake_get
os.environ["FINNHUB_API_KEY"] = "test-key"
check("with one, the whole day in one request", len(finnhub.calendar(DAY)), 4)
check("the key goes in a header, never in the address",
      ("test-key" in json.dumps(seen["params"]) or "test-key" in seen["url"],
       seen["headers"]["X-Finnhub-Token"]), (False, "test-key"))
os.environ.pop("FINNHUB_API_KEY", None)

print("\nThe reaction line:")
quotes = {"DE": {"name": "Deere & Company", "pre_pct": 3.4}}
rows = discord.reporter_rows("pre", ["DE"], quotes,
                             {"DE": finnhub.merged(None, found["DE"])}, {})
line = discord.reporters_message("pre", rows, DAY, "9:21 AM").splitlines()[1]
check("earnings and revenue, each against its estimate",
      ("EPS 4.12 against 3.90 expected (+5.6%)" in line,
       "revenue $10.58bn against $10.30bn (+2.7%)" in line), (True, True))
check("money the way a headline writes it",
      (discord.money(10_580_000_000), discord.money(812_000_000), discord.money(950_000)),
      ("$10.58bn", "$812m", "$950,000"))
rows = discord.reporter_rows("pre", ["DE"], quotes, {"DE": {**yahoo, "hour": dt.time(7, 0)}}, {})
check("a line built from Yahoo alone says nothing about revenue",
      "revenue" in discord.reporters_message("pre", rows, DAY, "9:21 AM"), False)

# ------------------------------------------------- reactions settling
print("\nReactions, settled:")
MON, TUE, WED = dt.date(2026, 11, 23), dt.date(2026, 11, 24), dt.date(2026, 11, 25)
waiting = [
    {"symbol": "PRE", "name": "Early Co", "day": TUE.isoformat(),
     "when": "before the bell", "move": 3.1, "implied": 7.0},
    {"symbol": "AFT", "name": "Late Co", "day": TUE.isoformat(),
     "when": "after the bell", "move": -8.0, "implied": 5.0},
    {"symbol": "OLD", "name": "Stale Co", "day": "2026-11-10",
     "when": "after the bell", "move": 1.0, "implied": None},
]
closes = {"PRE": {"session_pct": 5.2, "session_on": TUE.isoformat()},
          "AFT": {"session_pct": 0.4, "session_on": TUE.isoformat()}}
done, still = discord.settle(waiting, closes, TUE)
check("a before-the-bell report settles in that day's session",
      [(r["symbol"], r["session_move"], r["inside"]) for r in done], [("PRE", 5.2, True)])
check("an after-the-bell one waits for the next day's; an old one is dropped",
      [r["symbol"] for r in still], ["AFT"])
closes["AFT"] = {"session_pct": -9.4, "session_on": TUE.isoformat()}
check("a holiday: Yahoo still shows the last session traded, so it keeps waiting",
      discord.settle(still, closes, WED)[0], [])
closes["AFT"]["session_on"] = WED.isoformat()
done2, still2 = discord.settle(still, closes, WED)
check("the next session's close, and whether the priced move held",
      [(r["symbol"], r["session_move"], r["inside"]) for r in done2], [("AFT", -9.4, False)])
text = discord.reactions_settled_message(done + done2, WED).splitlines()
check("the biggest move first, with the quote the reaction line gave",
      text[1], "`AFT` Late Co: closed -9.4% · was -8.0% after the bell · "
               "options priced ±5.0%, outside")
check("nobody settled, nothing said", discord.reactions_settled_message([], WED), None)
check("a post that did not go out puts them back as they were",
      discord.unsettled(done)[0], waiting[0])
row = {"symbol": "DE", "name": "Deere", "move": 3.4, "when": "before the bell",
       "screen": "VCP", "implied": 7.6, "eps": 4.12, "estimate": 3.9,
       "surprise_pct": 5.6}
public = discord.public_row(row, WED, "pre", "2026-11-25T09:21")
check("the row a public page reads says nothing of which screen a name is on",
      ("screen" in public, public["eps"], public["day"]), (False, 4.12, "2026-11-25"))
check("a move read on the day is already its session's",
      (discord.awaits_session(row), discord.awaits_session({"when": "on the day"})),
      (True, False))

# ------------------------------------------------------ the S&P 500
print("\nThe S&P 500 list:")
from data import indexes                          # noqa: E402

LIST = "Symbol,Security,GICS Sector\n" + "".join(
    f"S{i},Company {i},Industrials\n" for i in range(500)) + "BRK.B,Berkshire,Financials\n" \
    "BF-B,Brown-Forman,Staples\n"
check("a share class is spelled with a dot, as the price feed spells it",
      [s for s in indexes.parse(LIST) if "." in s], ["BF.B", "BRK.B"])
book = sqlite3.connect(":memory:")
book.row_factory = sqlite3.Row
store.migrate(book)
check("before the first fetch nobody is tagged, and that is not 'not a member'",
      indexes.sp500(book), (set(), None))


class Page:
    def __init__(self, code, text):
        self.status_code, self.text = code, text


pages: list = []
indexes.requests.get = lambda url, timeout=None, headers=None: pages.pop(0)
pages[:] = [Page(200, LIST)]
said: list[str] = []
check("fetched and kept", indexes.refresh(book, dt.date(2026, 11, 25), said.append)["count"], 502)
check("not asked again within the week",
      (indexes.refresh(book, dt.date(2026, 11, 27), said.append)["status"], len(pages)),
      ("fresh", 0))
pages[:] = [Page(200, "Symbol,Security\nAAA,One\nBBB,Two\n")]
check("a list of the wrong size is not believed; the kept one stands",
      (indexes.refresh(book, dt.date(2026, 12, 3), said.append)["status"],
       len(indexes.sp500(book)[0])), ("kept", 502))
pages[:] = [Page(200, LIST.replace("S499,Company 499,Industrials\n", "NEW,Newcomer,Tech\n"))]
indexes.refresh(book, dt.date(2026, 12, 3), said.append)
check("a change in membership is said in the log",
      said[-1], "S&P 500 list refreshed: 502 lines. Joined: NEW. Left: S499.")

print()
if FAILED:
    print(f"{len(FAILED)} CHECK(S) FAILED: {FAILED}")
    sys.exit(1)
print("ALL DESK AND FINNHUB CHECKS PASS")
