"""Offline checks on the intraday quote sweep (catalysts.quotes, catalysts.yf).

Run: python tools/test_quotes.py
"""
from __future__ import annotations

import pathlib
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from catalysts import cboe, quotes, yf  # noqa: E402

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:62} {got!r}")
    if not ok:
        failures.append(label)


# ------------------------------------------------------------- one row
row = yf.quote_row(170.38, 175.34, 1795208403)
check("a row carries last, previous close and the move",
      (row["last"], row["prev_close"], row["change_pct"]), (170.38, 175.34, -2.83))
check("the trade time is New York wall time, no offset", row["at"], "2026-11-20T16:00:03")
check("no previous close: the move is unknown, not zero",
      yf.quote_row(10, None)["change_pct"], None)
check("no price: no row", yf.quote_row(0, 10), None)
check("a NaN price: no row", yf.quote_row(float("nan"), 10), None)
check("class shares take a dash for Yahoo", yf.yahoo_symbol("brk.b"), "BRK-B")


# ------------------------------------------------- the quote endpoint
class Response:
    def __init__(self, status, rows):
        self.status_code, self._rows = status, rows

    def json(self):
        return {"quoteResponse": {"result": self._rows}}


class FakeData:
    calls: list[list[str]] = []
    refuse_from = None

    def get(self, url, params=None):
        batch = params["symbols"].split(",")
        FakeData.calls.append(batch)
        if FakeData.refuse_from is not None and len(FakeData.calls) > FakeData.refuse_from:
            return Response(429, [])
        return Response(200, [
            {"symbol": s, "regularMarketPrice": 50.0, "regularMarketPreviousClose": 40.0,
             "regularMarketTime": 1795208403}
            for s in batch if s != "GONE"])


stub = types.ModuleType("yfinance.data")
stub.YfData = FakeData
real_data = sys.modules.get("yfinance.data")
sys.modules["yfinance.data"] = stub

names = [f"N{i}" for i in range(448)] + ["BRK.B", "GONE"]
got = yf._quotes_from_endpoint(object(), names)
check("450 names go in three requests", [len(c) for c in FakeData.calls], [200, 200, 50])
check("the dotted name comes back under its own spelling", got.get("BRK.B", {}).get("last"), 50.0)
check("a name Yahoo does not carry is simply absent", "GONE" in got, False)
check("everything else answered", len(got), 449)

FakeData.calls, FakeData.refuse_from = [], 1
yf.QUOTE_OUTCOMES.clear()
got = yf._quotes_from_endpoint(object(), names)
check("a refused request loses its own names only", len(got), 200)
check("and is counted", yf.QUOTE_OUTCOMES["batch_http_429"], 2)

# ----------------------------------------- endpoint, then the download
fake_yf = object()
yf._yf = lambda: fake_yf
downloads: list[int] = []


def no_download(_, symbols):
    downloads.append(len(symbols))
    return {s: yf.quote_row(9.0, 8.0) for s in symbols}


yf._quotes_from_download = no_download
FakeData.calls, FakeData.refuse_from = [], None
got = yf.quotes(names)
check("one missing name does not trigger a second pass", downloads, [])
check("the tally says how the names were answered",
      (yf.QUOTE_OUTCOMES["endpoint"], yf.QUOTE_OUTCOMES["missing"]), (449, 1))

FakeData.calls, FakeData.refuse_from = [], 0
got = yf.quotes(names)
check("the endpoint refusing everything sends them all to the download", downloads, [450])
check("and they are answered from it", (len(got), yf.QUOTE_OUTCOMES["download"]), (450, 450))


def boom(*_):
    raise RuntimeError("internals moved")


yf._quotes_from_endpoint, kept = boom, yf._quotes_from_endpoint
downloads.clear()
got = yf.quotes(["AAPL", "MSFT"])
check("the library's internals moving is survived", (len(got), downloads), (2, [2]))
yf._quotes_from_endpoint = kept
yf._yf = lambda: None
check("no library at all: nothing, and no error", yf.quotes(["AAPL"]), {})

# ------------------------------------------------------ the sweep
notes: list[str] = []
cboe_asked: list[str] = []


def cboe_answers(symbol):
    cboe_asked.append(symbol)
    cboe.OUTCOMES["ok"] += 1
    return {"last": 1.0, "prev_close": 1.0, "change_pct": 0.0, "at": None}


def cboe_refuses(symbol):
    cboe_asked.append(symbol)
    cboe.OUTCOMES["throttled"] += 1
    cboe.OUTCOMES["http_403"] += 1
    # What the real fetch does on a refusal: the stand-down counts names.
    cboe._refused_in_a_row += 1
    return None


def yahoo_returns(answer):
    def run(symbols):
        yf.QUOTE_OUTCOMES.clear()
        return {s: yf.quote_row(5.0, 4.0) for s in symbols if answer(s)}
    return run


wanted = [f"S{i}" for i in range(600)] + ["s0"]

quotes.yf.quotes = yahoo_returns(lambda s: True)
quotes.cboe.quote = cboe_answers
payload = quotes.collect(wanted, notice=notes.append)
check("duplicates are asked once", payload["wanted"], 600)
check("Yahoo answering everything leaves Cboe unasked", (payload["count"], cboe_asked), (600, []))
check("the file names its source", (payload["source"], payload["sources"]),
      ("yahoo-delayed", {"yahoo-delayed": 600}))

quotes.yf.quotes = yahoo_returns(lambda s: s not in ("S3", "S7"))
payload = quotes.collect(wanted, notice=notes.append)
check("Cboe is asked only for what Yahoo left", cboe_asked, ["S3", "S7"])
check("and both are named", payload["sources"], {"yahoo-delayed": 598, "cboe-delayed": 2})

cboe_asked.clear()
notes.clear()
quotes.yf.quotes = yahoo_returns(lambda s: False)
quotes.cboe.quote = cboe_refuses
payload = quotes.collect(wanted, notice=notes.append)
check("Cboe refusing from the start is left alone after twelve", len(cboe_asked), 12)
check("nothing answered is said plainly", any("NONE answered" in n for n in notes), True)
check("and the file says so", (payload["count"], payload["source"], payload["truncated"]),
      (0, "none", False))

cboe_asked.clear()
quotes.cboe.quote = cboe_answers
payload = quotes.collect(wanted, notice=notes.append)
check("with Yahoo down Cboe covers the nearest four hundred",
      (payload["count"], cboe_asked[0], cboe_asked[-1]), (400, "S0", "S399"))

if real_data is not None:
    sys.modules["yfinance.data"] = real_data

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL QUOTE CHECKS PASS")
