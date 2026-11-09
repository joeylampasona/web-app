"""Offline checks on the hourly headline run (catalysts.news.live).

Run: python tools/test_news_live.py
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from catalysts import news  # noqa: E402

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:56} {got!r}")
    if not ok:
        failures.append(label)


class Fake:
    api_key = "test"

    def __init__(self, pages):
        self.pages, self.asked = list(pages), []

    def _get(self, path, params=None):
        self.asked.append((path, params))
        return self.pages.pop(0) if self.pages else {"results": []}


def art(url, published, tickers, title="Acme wins a contract"):
    return {"article_url": url, "published_utc": published, "tickers": tickers,
            "title": title, "publisher": {"name": "Wire"}}


out = pathlib.Path(tempfile.mkdtemp())
(out / "news.json").write_text(json.dumps({
    "articles": [{"url": "u-old", "published_at": "2026-11-09T12:00:00Z", "tickers": ["AAA"],
                  "status": {"AAA": "setting_up"}}],
    "prominent_tickers": ["BIG"]}))
(out / "search.json").write_text(json.dumps({"rows": [{"symbol": s} for s in ("AAA", "BIG", "CCC")]}))
now = dt.datetime(2026, 11, 9, 20, 0, tzinfo=dt.timezone.utc)

fake = Fake([{"results": [
    art("u-new", "2026-11-09T19:00:00Z", ["AAA", "ZZZ"]),
    art("u-old", "2026-11-09T12:00:00Z", ["AAA"]),
    art("u-none", "2026-11-09T18:00:00Z", ["ZZZ"]),
    art("u-big", "2026-11-09T17:00:00Z", ["BIG"], "Rosen Law Firm reminds BIG investors"),
], "next_url": None}])
got = news.live(out, adapter=fake, now=now)
urls = [a["url"] for a in got["articles"]]
check("only new articles about followed names, newest first", urls, ["u-new", "u-big"])
check("asked only for what is newer than the nightly", fake.asked[0][1]["published_utc.gt"],
      "2026-11-09T12:00:00Z")
check("tickers trimmed to the ones followed", got["articles"][0]["tickers"], ["AAA"])
check("state carried from the nightly's articles", got["articles"][0]["status"], {"AAA": "setting_up"})
check("prominent from the nightly's list", got["articles"][1]["prominent"], True)
check("classified like the nightly", got["articles"][1]["kind"], news.classify_headline(
    "Rosen Law Firm reminds BIG investors"))

stale = Fake([])
(out / "news.json").write_text(json.dumps({"articles": [
    {"url": "x", "published_at": "2026-11-01T00:00:00Z", "tickers": ["AAA"]}]}))
news.live(out, adapter=stale, now=now)
check("a stale nightly reaches back 36 hours, not a week", stale.asked[0][1]["published_utc.gt"],
      "2026-11-08T08:00:00+00:00")

class NoKey:
    api_key = None
check("no key: nothing, and no error", news.live(out, adapter=NoKey(), now=now)["articles"], [])
check("no tree: nothing, and no error",
      news.live(pathlib.Path(tempfile.mkdtemp()), adapter=Fake([]), now=now)["articles"], [])

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL LIVE NEWS CHECKS PASS")
