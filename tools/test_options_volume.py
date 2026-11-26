"""Offline: the day's option volume, the volatility line, and the post that
goes out before the bell.

No network. A chain is a table of rows, Yahoo's two quotes are a dictionary.

    python tools/test_options_volume.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from catalysts import chains, iv, optvol, volatility   # noqa: E402
from data import store                                 # noqa: E402
from data.types import OptionChain                     # noqa: E402
from publish import discord, gated                     # noqa: E402

FAILED: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:<68} {got!r}"
          + ("" if ok else f"   want {want!r}"))
    if not ok:
        FAILED.append(label)


DAY = dt.date(2026, 11, 25)
DEC = dt.date(2026, 12, 18)
JAN = dt.date(2027, 1, 15)


def row(expiry, side, strike, volume, oi, fresh=True):
    return {"expiry": expiry, "side": side, "strike": float(strike), "oi": oi,
            "volume": volume, "fresh": fresh,
            "traded": DAY if fresh else dt.date(2026, 11, 3)}


# ---------------------------------------------------------- the arithmetic
print("A company's day in its options:")
QUOTED = [
    row(DEC, "call", 100, 4_000, 1_000),         # four times what was open
    row(DEC, "call", 105, 600, 5_000),
    row(DEC, "put", 95, 1_200, 800),
    row(DEC, "put", 90, 9_000, 100, fresh=False),  # last traded three weeks ago
    row(JAN, "call", 110, 12, 2),                # a multiple of six, and nothing
    row(JAN, "put", 100, 700, 0),                # traded with nothing open
]
BOOK = {(DEC, "call", 100.0): 1_000, (DEC, "call", 105.0): 5_000,
        (DEC, "put", 95.0): 800, (DEC, "put", 90.0): 100, (JAN, "call", 110.0): 2,
        (JAN, "put", 100.0): 0, (JAN, "call", 120.0): 3_000,      # Yahoo does not list it
        (dt.date(2027, 6, 18), "call", 100.0): 50_000}            # an expiry not asked about
found = optvol.summary("test", 100.0, [dict(r) for r in QUOTED], BOOK)
check("calls and puts, counted apart", (found["call_volume"], found["put_volume"]),
      (4_612, 1_900))
check("a contract that last traded weeks ago adds nothing to today",
      found["volume"], 6_512)
check("puts for every call", found["put_call"], 0.41)
check("open interest is the book on the expiries asked about, listed by Yahoo or not",
      found["open_interest"], 1_000 + 5_000 + 800 + 100 + 2 + 0 + 3_000)
check("the day's trading as a share of it", found["volume_oi"], round(6_512 / 9_902, 3))
check("the busiest contracts first",
      [(t["side"], t["strike"], t["volume"]) for t in found["top"][:3]],
      [("call", 100.0, 4_000), ("put", 95.0, 1_200), ("put", 100.0, 700)])
check("each with how many times its open interest it traded",
      [t["multiple"] for t in found["top"][:3]], [4.0, 1.5, None])
check("and how far its strike is from the price", found["top"][1]["vs_spot_pct"], -5.0)
check("the session is the day the fresh contracts traded", found["session"], "2026-11-25")
check("at most five are kept", len(found["top"]) <= optvol.TOP, True)

print("\nWhat counts as unusual:")
flags = {(t["side"], t["strike"]): t["unusual"] for t in found["top"]}
check("twice the open interest and five hundred contracts: unusual",
      flags[("call", 100.0)], True)
check("one and a half times is not", flags[("put", 95.0)], False)
check("twelve against two is a multiple of six and not a headline",
      flags[("call", 110.0)], False)
check("seven hundred with nothing open, by the clearing house's count: unusual",
      flags[("put", 100.0)], True)
check("so two contracts are", found["unusual"], 2)
alone = optvol.summary("test", 100.0, [dict(r) for r in QUOTED], None)
check("against Yahoo's own open interest a zero is Yahoo's, and not called unusual",
      ({(t["side"], t["strike"]): t["unusual"] for t in alone["top"]}[("put", 100.0)],
       alone["oi_source"], alone["unusual"]), (False, "yahoo", 1))
check("nothing traded and nothing open: no summary",
      optvol.summary("test", 100.0, [row(DEC, "call", 100, 0, 0)], None), None)
check("no rows: no summary", optvol.summary("test", 100.0, [], BOOK), None)
quiet = optvol.summary("test", 100.0, [row(DEC, "call", 100, 0, 500)], None)
check("a book nobody traded today is a summary with no volume, not an absence",
      (quiet["volume"], quiet["put_call"], quiet["volume_oi"]), (0, None, 0.0))

# ------------------------------------------------- it rides on the chain
print("\nIt rides on the chain already downloaded:")
asked: list[str] = []
chains.occ.open_interest = lambda symbol: BOOK


def fake_quoted(symbol, today, **kw):
    asked.append(symbol)
    return 100.0, [dict(r, iv=0.4, bid=1.0, ask=1.1) for r in QUOTED]


chains.yf.quoted_chain = fake_quoted
built = chains.build("TEST", DAY)
check("one request for the chain, and the volume comes with it",
      (len(asked), built.activity["volume"]), (1, 6_512))


class Adapter:
    def get_option_chain(self, symbol):
        return built if symbol == "TEST" else OptionChain(symbol=symbol, spot=10.0)


class Event:
    type, title, confirmed, date = "earnings", "Earnings", "confirmed", DAY + dt.timedelta(days=9)

    def days_until(self, as_of):
        return 9


class Calendar:
    as_of = DAY

    def next_owned(self, symbol):
        return Event()


volumes: dict = {}
iv.compute(Calendar(), ["TEST", "NONE"], {}, Adapter(), gamma_out={}, stats={},
           volume_out=volumes)
check("the stage keeps it for the names whose chain carried volume",
      sorted(volumes), ["TEST"])

# ---------------------------------------------------------------- storage
print("\nKept a row a session:")
conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
store.migrate(conn)
for back, volume in ((8, 900), (7, 1_100), (6, 1_000), (3, 1_000), (2, 1_000), (1, 1_000)):
    optvol.store(conn, {"TEST": {**found, "volume": volume}}, DAY - dt.timedelta(days=back))
optvol.store(conn, {"TEST": found, "THIN": {**found, "symbol": "THIN", "volume": 300}}, DAY)
loaded = optvol.load(conn, ["TEST", "THIN", "OTHER"], DAY)
check("the newest day for each name asked about", sorted(loaded), ["TEST", "THIN"])
check("with what is usual for it, from its own earlier sessions",
      (loaded["TEST"]["usual_volume"], loaded["TEST"]["usual_sessions"],
       loaded["TEST"]["vs_usual"]), (1_000, 6, 6.5))
check("nothing is called usual on fewer than five earlier sessions",
      (loaded["THIN"]["usual_volume"], loaded["THIN"]["vs_usual"]), (None, None))
check("a day stored for this edition is not stale", loaded["TEST"]["stale"], False)
later = optvol.load(conn, ["TEST"], DAY + dt.timedelta(days=2))
check("two days on it is shown, and said to be an earlier day's",
      (later["TEST"]["as_of"], later["TEST"]["stale"]), ("2026-11-25", True))
check("a week on it is not shown", optvol.load(conn, ["TEST"], DAY + dt.timedelta(days=9)), {})
optvol.store(conn, {"TEST": found}, DAY + dt.timedelta(days=60))
check("days older than the window are let go",
      conn.execute("SELECT COUNT(*) FROM options_volume").fetchone()[0], 1)

print("\nThe board, and what of it is free:")
names = {f"S{i:02d}": {"symbol": f"S{i:02d}", "volume": 2_000 + 100 * i,
                       "volume_oi": round(0.1 + i / 100, 3)} for i in range(12)}
names["TINY"] = {"symbol": "TINY", "volume": 1_500, "volume_oi": 9.0}
names["BARE"] = {"symbol": "BARE", "volume": 9_000, "volume_oi": None}
ranked = optvol.board(names)
check("ranked by the day's volume against open interest",
      [r["symbol"] for r in ranked[:3]], ["S11", "S10", "S09"])
check("a name under two thousand contracts is left off, whatever its ratio",
      "TINY" in {r["symbol"] for r in ranked}, False)
check("and one with no open interest to measure against",
      "BARE" in {r["symbol"] for r in ranked}, False)
free = gated.free_volume_symbols(ranked)
check("the top five rows stay public", sorted(free), ["S07", "S08", "S09", "S10", "S11"])
documents = gated.options_volume_documents(ranked, names, free, DAY, total=len(ranked))
paths = [d.path for d in documents]
check("subscribers get the whole board as one document", paths[0], "market/options_volume.json")
check("and each other company's own summary, but not the free ones'",
      ("stocks/options_volume/s00.json" in paths, "stocks/options_volume/s11.json" in paths),
      (True, False))

# -------------------------------------------------------- the volatility line
print("\nThe VIX against its three-month version:")
check("the near month priced above the three-month is stressed",
      volatility.state(24.0, 23.0), "stressed")
check("so is a VIX of thirty, whatever the curve", volatility.state(31.0, 36.0), "stressed")
check("the gap nearly closed is uneasy", volatility.state(18.0, 18.6), "uneasy")
check("so is a VIX of twenty with an ordinary curve", volatility.state(21.0, 24.0), "uneasy")
check("under fifteen and well under the three-month is calm",
      volatility.state(13.0, 16.0), "calm")
check("under fifteen with the curve nearly flat is not calm",
      volatility.state(14.0, 15.0), "ordinary")
check("everything else is ordinary", volatility.state(17.0, 19.5), "ordinary")
check("without the three-month figure the level alone decides",
      (volatility.state(13.0, None), volatility.state(22.0, None)), ("calm", "uneasy"))
check("the published reading",
      volatility.reading(18.42, 20.11, "2026-11-25"),
      {"as_of": "2026-11-25", "vix": 18.42, "vix3m": 20.11, "ratio": 0.916,
       "state": "ordinary"})
check("no VIX, no reading", volatility.reading(None, 20.0, "2026-11-25"), None)

conn.execute("CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT)")
volatility.settings.get = lambda key, default=None: "polygon" if key == "data.provider" else default
said: list[str] = []
volatility.refresh(conn, DAY - dt.timedelta(days=1), said.append,
                   fetch=lambda: volatility.reading(17.0, 19.5, "2026-11-24"))
volatility.refresh(conn, DAY, said.append,
                   fetch=lambda: volatility.reading(18.42, 20.11, "2026-11-25"))
newest = volatility.latest(conn, DAY)
check("the newest reading, with the one before it and where it came from",
      (newest["vix"], newest["previous_vix"], newest["source"]), (18.42, 17.0, "Yahoo"))
check("the log says the levels and the word",
      said[-1], "volatility: VIX 18.42, three-month 20.11, ratio 0.92: ordinary (2026-11-25).")


def broken():
    raise RuntimeError("Yahoo is down")


check("a night Yahoo fails keeps the last reading and stops nothing",
      (volatility.refresh(conn, DAY + dt.timedelta(days=1), said.append, fetch=broken),
       volatility.latest(conn, DAY + dt.timedelta(days=1))["as_of"]), (None, "2026-11-25"))
check("a night it has no VIX says so", (volatility.refresh(
    conn, DAY + dt.timedelta(days=1), said.append, fetch=lambda: None), said[-1]),
    (None, "volatility: Yahoo gave no VIX tonight; the last reading stands."))
check("a reading a week old is not the state of things",
      volatility.latest(conn, DAY + dt.timedelta(days=8)), None)

# ------------------------------------------------------- before the bell
print("\nBefore the bell:")
ON_SCREEN = {"UPP": "VCP", "BIG": "Blue sky", "DWN": "VCP", "FLAT": "VCP",
             "SHUT": "VCP", "GONE": "VCP"}
QUOTES = {
    "UPP": {"name": "Upp Holdings, Inc.", "pre_pct": 4.2, "state": "PRE"},
    "BIG": {"name": "Big Corp", "pre_pct": 11.8, "state": "PRE"},
    "DWN": {"name": "Down Co", "pre_pct": -6.5, "state": "PRE"},
    "FLAT": {"name": "Flat Co", "pre_pct": 1.1, "state": "PRE"},
    "SHUT": {"name": "Shut Co", "pre_pct": 9.0, "state": "CLOSED"},
    "OFF": {"name": "Off Screen", "pre_pct": 20.0, "state": "PRE"},
}
up, down = discord.premarket_movers(QUOTES, ON_SCREEN)
check("the largest moves first, each way", ([r["symbol"] for r in up],
                                            [r["symbol"] for r in down]),
      (["BIG", "UPP"], ["DWN"]))
check("a move under three per cent is not worth a line",
      "FLAT" in {r["symbol"] for r in up + down}, False)
check("a figure Yahoo does not mark as pre-market is not this morning's",
      "SHUT" in {r["symbol"] for r in up + down}, False)
check("a name on no screen is nobody's business here",
      "OFF" in {r["symbol"] for r in up + down}, False)
text = discord.premarket_message(up, down, DAY, "9:21 AM").splitlines()
check("the post: who, how far, which screen",
      text[1], "Up: `BIG` +11.8% (Blue sky) · `UPP` +4.2% (VCP)")
check("and the other way", text[2], "Down: `DWN` -6.5% (VCP)")
check("it says these are quotes in thin trading", "thin trading" in text[-1], True)
check("nothing moving, nothing said", discord.premarket_message([], [], DAY, "9:21 AM"), None)
many = {f"M{i:02d}": {"pre_pct": 3.0 + i, "state": "PRE"} for i in range(20)}
check("at most eight a side",
      len(discord.premarket_movers(many, {s: "VCP" for s in many})[0]),
      discord.PREMARKET_EACH_WAY)

# Once a day: the reporters run notes the day it went out and does not repeat it.
import json                                        # noqa: E402
import tempfile                                    # noqa: E402
import types                                       # noqa: E402

from cli import commands                           # noqa: E402

sent: list[str] = []
commands._names_on_screens = lambda out: dict(ON_SCREEN)
from catalysts import yf as yfmod                  # noqa: E402

yfmod.report_day_quotes = lambda symbols: dict(QUOTES)
discord.post = lambda room, content="", **kw: sent.append((room, content)) or True
out = pathlib.Path(tempfile.mkdtemp())
args = types.SimpleNamespace(send=True)
check("the morning's post goes out, to the edition room",
      (commands._premarket(args, out, DAY, "9:21 AM"), sent[0][0]), (True, "edition"))
check("a dry run prints it and sends nothing",
      (commands._premarket(types.SimpleNamespace(send=False), out, DAY, "9:21 AM"), len(sent)),
      (False, 1))
check("nothing about it is written to the published tree", list(out.iterdir()), [])

# The note that carries "already posted today", through a real reporters run.
commands.settings.out_dir = lambda: out
(out / "catalysts").mkdir()
(out / "catalysts" / "upcoming.json").write_text(json.dumps({"events": []}))
discord.which_run = lambda now: "pre"
state = out / "note.json"
state.write_text(json.dumps({"date": DAY.isoformat(), "premarket": None}))
run = types.SimpleNamespace(send=True, state=str(state), day=DAY.isoformat(), when="pre",
                            reads=False)
commands.cmd_reporters(run)
note = json.loads((out / "reporters.json").read_text())
check("the reporters note records the day it went out", note["premarket"], DAY.isoformat())
state.write_text(json.dumps(note))
before = len(sent)
commands.cmd_reporters(run)
check("and a second morning run does not send it again", len(sent) - before, 0)

print()
if FAILED:
    print(f"{len(FAILED)} CHECK(S) FAILED: {FAILED}")
    sys.exit(1)
print("ALL OPTION VOLUME CHECKS PASS")
