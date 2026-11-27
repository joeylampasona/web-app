"""Offline: the option chain joined from OCC's open interest and Yahoo's quotes.

No network. OCC's file is a string, Yahoo's rows are a table.

    python tools/test_chains.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from catalysts import chains, gamma, occ, yf   # noqa: E402

FAILED: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:<66} {got!r}"
          + ("" if ok else f"   want {want!r}"))
    if not ok:
        FAILED.append(label)


TODAY = dt.date(2026, 11, 25)
DEC = dt.date(2026, 12, 18)
JAN = dt.date(2027, 1, 15)
JUN = dt.date(2027, 6, 18)

# ------------------------------------------------------- OCC's series file
FILE = """Series Search Results for TEST

Products for this underlying symbol are traded on:
AMEX ARCA CBOE

\t\tSeries/contract\t\tStrike\t\t\tOpen Interest\t\t\t
ProductSymbol\tyear\tMonth\tDay\tInteger\tDec\tC/P\tCall\tPut\tPosition Limit\t
TEST  \t\t2026\t12\t18\t95\t000\tC P \t100\t900\t250000
TEST  \t\t2026\t12\t18\t100\t000\tC P \t500\t400\t250000
TEST  \t\t2026\t12\t18\t105\t000\tC P \t800\t50\t250000
TEST  \t\t2026\t12\t18\t102\t500\tC P \t70\t0\t250000
TEST  \t\t2027\t01\t15\t100\t000\tC P \t300\t200\t250000
TEST  \t\t2027\t06\t18\t100\t000\tC P \t1000\t2000\t250000
TEST1 \t\t2026\t12\t18\t100\t000\tC P \t9999\t9999\t250000
"""
print("OCC's series file:")
book = occ.parse(FILE)
check("each series, both sides", len(book), 12)
check("a call's open interest", book[(DEC, "call", 105.0)], 800)
check("a put's", book[(DEC, "put", 95.0)], 900)
check("a strike with thousandths", book[(DEC, "call", 102.5)], 70)
check("an adjusted root is left out", book[(DEC, "call", 100.0)], 500)
check("a page that is not the file", occ.parse("<html>Attention Required</html>"), None)
check("a share class is spelled without its dot", occ.spelling("brk.b"), "BRKB")


class Reply:
    def __init__(self, code, text=""):
        self.status_code, self.text = code, text


answers: list[Reply] = []
asked: list[dict] = []


def fake_get(url, params=None, headers=None, timeout=None):
    asked.append({"url": url, "params": params, "agent": headers["User-Agent"]})
    return answers.pop(0) if answers else Reply(503)


occ.requests.get = fake_get
occ.time.sleep = lambda seconds: None

answers[:] = [Reply(200, FILE)]
check("answered: the book", len(occ.open_interest("TEST")), 12)
check("asked under a plain name, not the SEC contact", asked[-1]["agent"], "tape-research")
check("by underlying", asked[-1]["params"], {"symbolType": "U", "symbol": "TEST"})
answers[:] = [Reply(404)]
check("a symbol it does not know: nothing listed", occ.open_interest("NOPE"), {})
answers[:] = [Reply(200, "No data exists for WINA symbol")]
check("a company with no listed options, in OCC's own words", occ.open_interest("WINA"), {})
answers[:] = [Reply(403), Reply(503)]
check("refused or down: no answer, which is different", occ.open_interest("TEST"), None)
answers[:] = [Reply(200, "<html>Attention Required</html>")]
check("a block page that answers 200 is not an empty book", occ.open_interest("TEST"), None)

occ.reset()
occ.OUTCOMES.clear()
answers[:] = []
before = len(asked)
for _ in range(occ.FAILURES_BEFORE_STANDING_DOWN + 5):
    occ.open_interest("TEST")
check("after enough silence in a row the rest are not asked",
      (occ.standing_down(), len(asked) - before, occ.OUTCOMES["not_asked"]),
      (True, occ.FAILURES_BEFORE_STANDING_DOWN * 2, 5))
occ.reset()
occ.OUTCOMES.clear()

# ------------------------------------------------------------- the join
print("\nThe join:")


def row(expiry, side, strike, iv, oi=5, bid=1.0, ask=1.1):
    return {"expiry": expiry, "side": side, "strike": float(strike), "oi": oi,
            "iv": iv, "bid": bid, "ask": ask}


QUOTED = [
    row(DEC, "call", 95, 0.40),
    row(DEC, "call", 100, 0.00001, bid=0.0, ask=0.0),     # nobody has quoted it
    row(DEC, "call", 105, 0.38),
    row(DEC, "put", 95, 0.42),
    row(DEC, "put", 100, 0.41),
    row(DEC, "put", 105, 0.90, bid=0.10, ask=3.00),        # a quote left over
    row(JAN, "call", 100, 0.36),
    row(JAN, "put", 100, 0.37),
]


def fresh():
    return [dict(r) for r in QUOTED]


joined = chains.join("test", 100.0, fresh(), book)
held = {(c.expiry, c.side, c.strike): c for c in joined.rows}
check("the chain says where it came from", joined.source, "occ+yahoo")
check("open interest is the clearing house's, not Yahoo's",
      held[(DEC, "call", 105.0)].open_interest, 800)
check("a contract nobody quoted takes the nearest strike's volatility",
      held[(DEC, "call", 100.0)].implied_volatility, 0.40)
check("a quote too wide to be a price is not a reading either",
      held[(DEC, "put", 105.0)].implied_volatility, 0.41)
check("a series only OCC lists is kept, on an expiry Yahoo was asked about",
      (held[(DEC, "call", 102.5)].open_interest,
       held[(DEC, "call", 102.5)].implied_volatility), (70, 0.38))
check("a series with nothing outstanding is dropped", (DEC, "put", 102.5) in held, False)
check("an expiry Yahoo was not asked about adds nothing", (JUN, "call", 100.0) in held, False)
check("every expiry asked about has its reading",
      [(e.expiry, e.contracts) for e in joined.expiries], [(DEC, 4), (JAN, 2)])
check("the reading uses quoted volatilities only, never borrowed ones",
      round(joined.expiries[0].implied_volatility, 4), round((0.40 + 0.38 + 0.42 + 0.41) / 4, 4))

stale = fresh() + [row(JAN, "call", 110, 1.60, bid=0.0, ask=0.0),
                   dict(row(JAN, "put", 90, 0.55, bid=0.0, ask=0.0), fresh=True)]
book_two = dict(book)
book_two[(JAN, "call", 110.0)] = 40
book_two[(JAN, "put", 90.0)] = 60
book_two[(JUN, "call", 100.0)] = 1000
later = chains.join("test", 100.0, stale + [row(JUN, "call", 100, 0.0, bid=0.0, ask=0.0)],
                    book_two)
held_later = {(c.expiry, c.side, c.strike): c.implied_volatility for c in later.rows}
check("no quote and no trade today: the figure is from an old trade, not believed",
      held_later[(JAN, "call", 110.0)], 0.36)
check("no quote but it traded on the latest session: believed",
      held_later[(JAN, "put", 90.0)], 0.55)
check("an expiry with nothing believed takes the nearest expiry's",
      held_later[(JUN, "call", 100.0)], 0.36)

alone = chains.join("test", 100.0, fresh(), None)
check("without OCC, Yahoo's own open interest stands and the chain says so",
      (alone.source, sum(c.open_interest for c in alone.rows)), ("yahoo", 40))
check("which gamma marks as a partial book",
      (gamma.profile(joined, TODAY).to_json()["book"],
       gamma.profile(alone, TODAY).to_json()["book"]), ("full", "partial"))
check("and the full book is the bigger one",
      gamma.profile(joined, TODAY).open_interest > gamma.profile(alone, TODAY).open_interest,
      True)
check("no rows, or no price for the company: no chain",
      (chains.join("test", 100.0, [], book), chains.join("test", 0.0, fresh(), book)),
      (None, None))
check("a tight quote, a wide one, a nickel-wide one on a cheap contract",
      (chains.wide(1.00, 1.10), chains.wide(0.10, 3.00), chains.wide(0.05, 0.10)),
      (False, True, False))

# ------------------------------------------------------------ the build
print("\nThe build:")
yahoo_asked: list[str] = []


def fake_quoted(symbol, today, **kw):
    yahoo_asked.append(symbol)
    return 100.0, fresh()


yf.quoted_chain = fake_quoted
chains.OUTCOMES.clear()

answers[:] = [Reply(200, FILE)]
check("OCC and Yahoo both answer", chains.build("TEST", TODAY).source, "occ+yahoo")

empty = FILE.replace("\t100\t900\t", "\t0\t0\t").replace("\t500\t400\t", "\t0\t0\t") \
            .replace("\t800\t50\t", "\t0\t0\t").replace("\t70\t0\t", "\t0\t0\t") \
            .replace("\t300\t200\t", "\t0\t0\t").replace("\t1000\t2000\t", "\t0\t0\t")
answers[:] = [Reply(200, empty)]
before = len(yahoo_asked)
check("OCC holds nothing for the company: no chain", chains.build("TEST", TODAY), None)
check("and Yahoo is not asked", len(yahoo_asked) - before, 0)

answers[:] = [Reply(200, "No data exists for TEST symbol")]
before = len(yahoo_asked)
check("OCC has never heard of it: no chain, Yahoo not asked",
      (chains.build("TEST", TODAY), len(yahoo_asked) - before), (None, 0))

answers[:] = [Reply(403), Reply(403)]
check("OCC silent: Yahoo's own open interest, marked", chains.build("TEST", TODAY).source,
      "yahoo")
check("each outcome is counted", dict(chains.OUTCOMES),
      {"occ+yahoo": 1, "no_listed_options": 2, "yahoo": 1})

# ------------------------------------------------- Yahoo saying slow down
print("\nYahoo's rate limit:")


class YFRateLimitError(Exception):
    pass


yf.time_sleep_calls = []
import time as _time                                # noqa: E402

_time.sleep = lambda seconds: yf.time_sleep_calls.append(seconds)
yf.reset_chains()
yf.CHAIN_OUTCOMES.clear()


def limited():
    raise YFRateLimitError("Too Many Requests")


stood_down = 0
for _ in range(3):
    try:
        yf._chain_request(limited)
    except yf._StoodDown:
        stood_down += 1
check("three in a row and Yahoo is left alone", (yf.chains_standing_down(), stood_down),
      (True, 3))
check("it waited once before giving up on the first request",
      yf.time_sleep_calls.count(yf.RATE_LIMIT_WAIT), 1)
yf.reset_chains()
check("an answer clears the count", (yf._chain_request(lambda: 7), yf.chains_standing_down()),
      (7, False))

# ------------------------------------------------------- the night's clock
print("\nThe night's clock:")
calls = {"occ": 0}
real_open_interest = occ.open_interest


def counted_occ(symbol):
    calls["occ"] += 1
    return {}


occ.open_interest = counted_occ
chains.OUTCOMES.clear()
now = {"t": 1000.0}
real_out_of_time = chains.out_of_time
chains.out_of_time = lambda clock=None: real_out_of_time(clock=lambda: now["t"])
chains.reset_budget()
chains.build("AAA", TODAY)
now["t"] += chains.TIME_BUDGET_SECONDS + 1
check("past the budget, the rest get no chain and OCC is not asked",
      (chains.build("BBB", TODAY), calls["occ"], chains.OUTCOMES["out_of_time"]),
      (None, 1, 1))
chains.reset_budget()
yf.reset_chains()
yf._rate_limited_in_a_row = yf.RATE_LIMITS_BEFORE_STANDING_DOWN
before = calls["occ"]
check("once Yahoo has stood down, OCC is not asked either",
      (chains.build("CCC", TODAY), calls["occ"] - before, chains.OUTCOMES["yahoo_stood_down"]),
      (None, 0, 1))
yf.reset_chains()
chains.out_of_time = real_out_of_time
occ.open_interest = real_open_interest

print("\nThe kept CPI and jobs dates:")
from catalysts import releases as rel  # noqa: E402

as_of = dt.date(2026, 11, 27)
horizon = as_of + dt.timedelta(days=90)
fred = [rel.Release(dt.date(2026, 12, 10), 10, "Consumer Price Index", True)]
filled = rel.with_schedule(fred, as_of, horizon)
check("dates FRED does not list yet are filled from the kept schedule",
      [r.date.isoformat() for r in filled if r.name == "Employment Situation"],
      ["2026-12-04", "2027-01-08", "2027-02-05"])
check("a date FRED has is not repeated", sum(1 for r in filled if r.date == dt.date(2026, 12, 10)), 1)
moved = rel.with_schedule([rel.Release(dt.date(2026, 12, 15), 10, "Consumer Price Index", True)],
                          as_of, horizon)
check("a release FRED has moved keeps FRED's date and not the kept one",
      [r.date.isoformat() for r in moved if r.name == "Consumer Price Index"][:2],
      ["2026-12-15", "2027-01-13"])
check("the kept dates link to FRED's own release page",
      next(r for r in filled if r.name == "Employment Situation").to_json(as_of)["link"],
      "https://fred.stlouisfed.org/release?rid=50")

print()
if FAILED:
    print(f"{len(FAILED)} CHECK(S) FAILED: {FAILED}")
    sys.exit(1)
print("ALL CHAIN CHECKS PASS")
