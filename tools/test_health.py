"""Offline checks on the nightly source report and the things that feed it.

Run: python tools/test_health.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from catalysts import cboe, gamma  # noqa: E402
from data.types import OptionChain, OptionContract  # noqa: E402
from publish import health  # noqa: E402

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:60} {got!r}")
    if not ok:
        failures.append(label)


conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.execute("CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT)")
conn.execute("CREATE TABLE bars(symbol TEXT, date TEXT, close REAL, volume REAL)")
for day in ("2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"):
    conn.executemany("INSERT INTO bars VALUES (?,?,?,?)",
                     [(s, day, 10.0, 1000.0) for s in ("AAA", "BBB", "CCC")])
conn.commit()
session = dt.date(2026, 11, 20)

# ------------------------------------------------------------ judging
check("everything answered is ok", health.judge(400, 394), "ok")
check("under four fifths answered is partial", health.judge(400, 300), "partial")
check("nothing answered is down", health.judge(400, 0), "down")
check("nothing asked is ok, not down", health.judge(0, 0), "ok")
check("a stage's own sentence gives the counts",
      health.counted("91 names fetched tonight, 2,586 of 2,639 have a date in total."),
      (2586, 2639))
check("a sentence with no counts gives none", health.counted("nothing to say"), (None, None))

# ------------------------------------------------------- the listener
said: list[str] = []
heard = health.Listener(said.append).keep("earnings_dates", "names fetched tonight")
heard("earnings: 2,530 names already have a recent date, asking about 109.")
heard("earnings: 91 names fetched tonight, 2,586 of 2,639 have a date in total.")
heard("earnings: 16 names fetched tonight, 2,585 of 2,639 have a date in total.")
check("every notice still reaches the log", len(said), 3)
check("the first summary is the one kept", heard.kept["earnings_dates"][:19], "earnings: 91 names ")

# --------------------------------------------------------- the report
health.record(conn, "options", session,
              "0 full books from Cboe, 1,150 shorter books from Yahoo, 58 with none.",
              asked=1208, answered=1150, status="partial")
health.record(conn, "forecasts", session, "394 of 400 asked about tonight came back with data.",
              asked=400, answered=394)
health.record(conn, "filings", dt.date(2026, 11, 19), "Asked about 107 companies.",
              asked=107, answered=107)
desk = {"as_of": "2026-11-18", "stage_status": {"filings": "ok", "tape": "ok"}}
rows = health.report(conn, session, desk, provider="polygon")
by = {row["key"]: row for row in rows}
check("rows come out in publishing order", [row["key"] for row in rows],
      ["prices", "options", "forecasts", "filings", "desk"])
check("prices are judged from the stored bars",
      (by["prices"]["status"], by["prices"]["detail"]), ("ok", "3 daily bars for 2026-11-20."))
check("and named for the provider", by["prices"]["from"], "Polygon")
check("a status given by the stage is kept", by["options"]["status"], "partial")
check("a healthy stage is ok", by["forecasts"]["status"], "ok")
check("a stage that did not run for this session is behind", by["filings"]["status"], "behind")
check("and says which session it last read",
      by["filings"]["detail"].startswith("Not refreshed for this edition; last read for 2026-11-19."),
      True)
check("the desk two sessions back is behind",
      (by["desk"]["status"], by["desk"]["detail"]),
      ("behind", "Last run covers 2026-11-18, two sessions before this edition."))
check("a source with nothing recorded is left out", "news" in by, False)
check("the summary lists only what is not ok",
      [line.split(" (")[0] for line in health.summary(rows)],
      ["Option chains", "Company filings", "Market Desk"])

desk["as_of"] = "2026-11-19"
row = {r["key"]: r for r in health.report(conn, session, desk)}["desk"]
check("the desk one session back is the ordinary state", row["status"], "ok")
desk["stage_status"]["tape"] = "failed"
row = {r["key"]: r for r in health.report(conn, session, desk)}["desk"]
check("a desk stage that failed makes it partial",
      (row["status"], row["detail"].endswith("Stages not reporting ok: tape.")), ("partial", True))
check("a session with no bars is prices down",
      {r["key"]: r for r in health.report(conn, dt.date(2026, 11, 23))}["prices"]["status"],
      "down")

# ------------------------------------------- which book gamma came from
def chain(source: str) -> OptionChain:
    expiry = session + dt.timedelta(days=28)
    rows = [OptionContract(expiry=expiry, side=side, strike=strike,
                           open_interest=500, implied_volatility=0.4)
            for strike in (95.0, 100.0, 105.0) for side in ("call", "put")]
    return OptionChain(symbol="AAA", spot=100.0, rows=rows, source=source)


check("a Cboe chain is the full book", gamma.profile(chain("cboe"), session).to_json()["book"], "full")
check("a Yahoo chain is a partial book", gamma.profile(chain("yahoo"), session).to_json()["book"],
      "partial")
check("a source that says nothing is not labelled", gamma.profile(chain(""), session).to_json()["book"],
      None)

# --------------------------------------------- Cboe standing down
class Reply:
    def __init__(self, code):
        self.status_code = code

    def json(self):
        return {"data": {"current_price": 5.0, "prev_day_close": 4.0}}


class Session:
    def __init__(self, codes):
        self.codes, self.calls = list(codes), 0

    def get(self, url, timeout=None, headers=None):
        self.calls += 1
        self.agent = headers["User-Agent"]
        return Reply(self.codes.pop(0) if self.codes else 403)


cboe.PAUSE = cboe.THROTTLE_PAUSE = 0
cboe.reset()
cboe.OUTCOMES.clear()
fake = Session([])
cboe._session = lambda: fake
for i in range(40):
    cboe.quote(f"S{i}")
check("twelve refused names, two tries each, then no more requests", fake.calls, 24)
check("the rest are counted as not asked", cboe.OUTCOMES["not_asked"], 28)
check("the host is given a plain name, not the contact string", fake.agent, "tape-research")

cboe.reset()
cboe.OUTCOMES.clear()
fake = Session([403, 403] * 11 + [200] + [403, 403] * 11 + [404] + [403, 403] * 5)
for i in range(29):
    cboe.quote(f"S{i}")
check("an answer in between starts the count again", cboe.standing_down(), False)
check("and so does a company that simply has no quote", cboe.OUTCOMES.get("not_asked", 0), 0)

# ------------------------------------- an implied volatility that is not one
from catalysts import iv as ivmod  # noqa: E402

check("an ordinary implied volatility is believed", ivmod.plausible(0.453), True)
check("one of a thousandth of a per cent is not", ivmod.plausible(0.00001), False)
check("nor is nothing at all", (ivmod.plausible(None), ivmod.plausible(float("nan"))),
      (False, False))

# ------------------------------- asking SEC again the same day
import json  # noqa: E402

from data import fundamentals  # noqa: E402

book = sqlite3.connect(":memory:")
book.row_factory = sqlite3.Row
book.execute("CREATE TABLE fundamentals_xbrl(symbol TEXT PRIMARY KEY, fetched_at TEXT, payload TEXT)")
today = dt.date(2026, 11, 21)
book.execute("INSERT INTO fundamentals_xbrl VALUES (?,?,?)",
             ("WSM", "2026-11-21 07:30:00", json.dumps({"period_end": "2026-08-02"})))
book.execute("INSERT INTO fundamentals_xbrl VALUES (?,?,?)",
             ("VVV", "2026-11-21 07:30:00", json.dumps({"period_end": "2026-09-30"})))
told = {"WSM": [dt.date(2026, 11, 19)], "VVV": [dt.date(2026, 11, 19)]}
check("the nightly's rule: asked today is not asked again", fundamentals.due(book, told, today), [])
check("the daytime runs ask again, and only those still on the old quarter",
      fundamentals.due(book, told, today, again=True), ["WSM"])

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL SOURCE REPORT CHECKS PASS")
