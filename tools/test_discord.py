"""Offline checks on what goes to Discord (publish.discord, and stop press in
the quotes command).

Run: python tools/test_discord.py
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import pathlib
import sys
import tempfile
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from cli import commands  # noqa: E402
from digest import alerts  # noqa: E402
from publish import discord  # noqa: E402

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok ' if ok else 'FAIL'} {label:62} {got!r}"[:200])
    if not ok:
        failures.append(label)


for name in ("DISCORD_WEBHOOK_URL", *discord.ROOMS.values(), "SITE_URL"):
    os.environ.pop(name, None)

# ----------------------------------------------------------- the rooms
check("no webhook at all: no room", discord.hook("edition"), "")
os.environ["DISCORD_WEBHOOK_URL"] = "https://hooks.example/one"
check("a room without its own webhook uses the shared one",
      discord.hook("stop_press"), "https://hooks.example/one")
check("so every room is the same room", discord.same_room("edition", "ops"), True)
os.environ["DISCORD_WEBHOOK_OPS"] = "https://hooks.example/ops"
check("a room with its own webhook uses it", discord.hook("ops"), "https://hooks.example/ops")
check("and is then a different room", discord.same_room("edition", "ops"), False)

sent: list[tuple[str, dict, dict]] = []


def opener(request, timeout=None):
    sent.append((request.full_url, json.loads(request.data), dict(request.header_items())))
    return io.BytesIO(b"")


check("a post goes out", discord.post("ops", "x" * 3000, username="Ops", opener=opener), True)
url, body, headers = sent[-1]
check("to that room's webhook", url, "https://hooks.example/ops")
check("cut to what Discord allows", len(body["content"]), discord.LIMIT)
check("under the name given, and a named agent", (body["username"], headers["User-agent"]),
      ("Ops", discord.AGENT))

# ------------------------------------------------- waiting for the site
class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


answers = iter(["2026-11-19", "2026-11-19", "2026-11-20"])
naps: list[int] = []
check("the site is waited for until it carries the session",
      discord.site_has("2026-11-20", wait_seconds=600, pause=20, sleep=naps.append,
                       opener=lambda r, timeout=None: Reply(json.dumps(
                           {"as_of": next(answers)}).encode())), True)
check("asking again after each pause", naps, [20, 20])


def refuses(request, timeout=None):
    raise OSError("down")


check("a site that never answers is given up on, not waited on for ever",
      discord.site_has("2026-11-20", wait_seconds=0, sleep=naps.append, opener=refuses), False)

# ----------------------------------------------------------- the edition
meta = {"as_of": "2026-11-20", "universe_count": 2639,
        "screens": [{"name": "VCP", "total": 386, "stages": {"fresh_breakout": 2, "forming": 40}},
                    {"name": "Flat base", "total": 306, "stages": {"forming": 12}}],
        "lost_leaders": ["META"], "lost_leader_reasons": {"META": "SEC refused"},
        "fomc": {"stale": False},
        "sources": [{"label": "Prices", "status": "ok", "detail": "fine"},
                    {"label": "Market Desk", "status": "behind",
                     "detail": "Last run covers 2026-11-18, two sessions before this edition."}]}
edition = {"headline": "Mixed", "blurb": "Some of it is working.",
           "meter": [{"score": 1}, {"score": -1}, {"score": 1}, {"score": 0}],
           "checks": ["SPY is 11.4% above its 200-day average."]}
content, embeds = discord.edition_message(meta, edition)
check("the post opens with the session as a day", content.splitlines()[0],
      "**Friday 11/20 close**: 2,639 names scanned.")
check("one line a screen", content.splitlines()[1], "  VCP: 386 (2 fresh, 40 forming)")
check("the card says how many checks are in gear", embeds[0]["title"],
      "Mixed: 2 of 4 checks in gear")
check("links to the back issue", embeds[0]["url"], "https://thetape.cc/market/editions/2026-11-20")
check("and carries the picture, addressed by session", embeds[0]["image"]["url"],
      "https://thetape.cc/share/read.png?v=2026-11-20")
check("no picture when the site has not caught up",
      "image" in discord.edition_message(meta, edition, picture=False)[1][0], False)
check("no edition on file: the counts alone", discord.edition_message(meta, None)[1], [])
check("a day behind is said in the first line",
      "1 day(s) behind" in discord.edition_message(meta, edition, behind=1)[0], True)
ops = discord.ops_lines(meta)
check("operations hears about a dropped leader", ops[1], "  META: SEC refused")
check("and a source that was behind", ops[-1].startswith("  Market Desk (behind): Last run"), True)
check("a clean night says nothing",
      discord.ops_lines({"sources": [{"label": "Prices", "status": "ok", "detail": ""}]}), [])

# ----------------------------------------------------------- stop press
day = dt.date(2026, 11, 23)
at = "2026-11-23T11:00:00"                     # 90 of 390 minutes gone
check("volume pace is volume against the share of the day gone",
      round(discord.volume_pace({"volume": 900_000, "avg_volume": 1_300_000, "at": at}), 2), 3.0)
check("no average volume: no pace", discord.volume_pace({"volume": 9, "at": at}), None)
check("the first minutes of the session give no pace",
      discord.volume_pace({"volume": 9, "avg_volume": 9, "at": "2026-11-23T09:40:00"}), None)

screens = [{"name": "VCP", "setups": {"forming": [
    {"symbol": "AAA", "name": "Alpha", "pivot": 100.0},
    {"symbol": "BBB", "name": "Beta", "pivot": 50.0},
    {"symbol": "CCC", "name": "Gamma", "pivot": 20.0},
    {"symbol": "DDD", "name": "Delta", "pivot": 10.0},
    {"symbol": "EEE", "name": "Epsilon", "pivot": 30.0}]}},
    {"name": "Rising wedge", "direction": "short", "setups": {"forming": [
        {"symbol": "SSS", "name": "Short", "pivot": 40.0}]}}]
quotes = {
    "AAA": {"last": 102.0, "volume": 900_000, "avg_volume": 1_300_000, "at": at},   # 3.0x
    "BBB": {"last": 51.0, "volume": 300_000, "avg_volume": 1_300_000, "at": at},    # 1.0x
    "CCC": {"last": 19.9, "volume": 900_000, "avg_volume": 1_300_000, "at": at},    # under
    "DDD": {"last": 10.5, "volume": 900_000, "avg_volume": 1_300_000,
            "at": "2026-11-20T15:59:00"},                                           # Friday's
    "EEE": {"last": 30.9, "volume": 1_500_000, "avg_volume": 1_300_000, "at": at},  # 5.0x
    "SSS": {"last": 39.0, "volume": 900_000, "avg_volume": 1_300_000, "at": at},    # a short
}
levels = alerts.forming_levels(screens)
events = alerts.detect(levels, quotes, list(levels))
names = {"AAA": "Alpha", "EEE": "Epsilon"}
rows = discord.crossings(events, quotes, names, session=day, already=set())
check("through the pivot, today, on volume: heaviest first",
      [r["symbol"] for r in rows], ["EEE", "AAA"])
check("a name already posted today is not posted again",
      [r["symbol"] for r in discord.crossings(events, quotes, names, session=day,
                                              already={"EEE"})], ["AAA"])
check("the cap holds", len(discord.crossings(events, quotes, names, session=day,
                                             already=set(), most=1)), 1)
message = discord.stop_press_message(rows, "11:04 AM")
check("the post says the prices are delayed and when they were read",
      message.splitlines()[0], "**Stop press**: delayed prices, read 11:04 AM ET")
check("one line a name, with the level, the volume and the screen",
      message.splitlines()[1],
      "`EEE` Epsilon: +3.0% over its 30.00 pivot, 5.0× the usual volume by now. "
      "VCP. <https://thetape.cc/stocks/EEE>")

# The command: what was posted is remembered for the day, and only the day.
out = pathlib.Path(tempfile.mkdtemp())
state = out / "last.json"
state.write_text(json.dumps({"date": day.isoformat(), "posted": ["EEE"]}))
posted: list[str] = []
alerts.in_session = lambda now: True
discord.post = lambda room, content, **kw: posted.append(content) or True


class Monday(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 23, 16, 4, tzinfo=dt.timezone.utc)


commands.dt = types.SimpleNamespace(datetime=Monday, timezone=dt.timezone, date=dt.date)
args = types.SimpleNamespace(stop_press_state=str(state), send_stop_press=True)
commands._stop_press(args, out, screens, quotes)
kept = json.loads((out / "stop_press.json").read_text())
check("only the new name is posted", ("`AAA`" in posted[0], "`EEE`" in posted[0]), (True, False))
check("and both are remembered for the day", kept, {"date": "2026-11-23", "posted": ["AAA", "EEE"]})
state.write_text(json.dumps({"date": "2026-11-20", "posted": ["AAA", "EEE"]}))
posted.clear()
commands._stop_press(args, out, screens, quotes)
check("a note from another day is not carried into this one",
      ("`AAA`" in posted[0], "`EEE`" in posted[0]), (True, True))
posted.clear()
args.send_stop_press = False
(out / "stop_press.json").unlink()
commands._stop_press(args, out, screens, quotes)
check("a dry run posts nothing and marks nothing",
      (posted, json.loads((out / "stop_press.json").read_text())["posted"]), ([], []))
commands.dt = dt

# -------------------------------------------------------------- the wrap
follow = {"screens": {
    "vcp": {"name": "VCP", "breakouts": [
        {"symbol": "AAA", "breakout_date": "2026-11-17", "now_pct": 6.0, "now_below_pivot": False},
        {"symbol": "BBB", "breakout_date": "2026-11-18", "now_pct": -3.0, "now_below_pivot": True},
        {"symbol": "OLD", "breakout_date": "2026-11-12", "now_pct": 9.0, "now_below_pivot": False}]},
    "flat_base": {"name": "Flat base", "breakouts": [
        {"symbol": "AAA", "breakout_date": "2026-11-17", "now_pct": 6.0, "now_below_pivot": False},
        {"symbol": "CCC", "breakout_date": "2026-11-20", "now_pct": 1.0, "now_below_pivot": False}]}}}
editions = {"editions": [
    {"date": "2026-11-20", "headline": "Mixed", "breakouts": 14, "failed": 24},
    {"date": "2026-11-19", "headline": "Risk on", "breakouts": 16, "failed": 23},
    {"date": "2026-11-13", "headline": "Risk off", "breakouts": 1, "failed": 2}]}
text = discord.wrap_message(follow, editions, dt.date(2026, 11, 20))
lines = text.splitlines()
check("the wrap names its week", lines[0], "**The week on the tape**: 11/16 to 11/20")
check("the reads in order, this week's only", lines[1],
      "The read each night: Thu Risk on · Fri Mixed")
check("the market's own tally for the week", lines[2],
      "Across the market, 30 closes through a pivot and 47 tests that fell back.")
check("a name on two screens broke out once, and last week's is left out",
      lines[3].startswith("On the base screens, 3 broke out. 2 still sit above the pivot "
                          "at Friday's close, 1 closed back under it."), True)
check("the furthest above, with screen and day", lines[4],
      "Furthest above: `AAA` +6.0% (VCP, Tue), `CCC` +1.0% (Flat base, Fri), "
      "`BBB` -3.0% (VCP, Wed)")
check("it ends on the page that has them all", lines[-1],
      "Every breakout and how it went: https://thetape.cc/market/followthrough")
check("a week with nothing at all says nothing",
      discord.wrap_message({"screens": {}}, {"editions": []}, dt.date(2026, 11, 20)), None)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL DISCORD CHECKS PASS")
