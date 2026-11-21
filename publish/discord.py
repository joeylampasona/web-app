"""What goes to Discord, and to which room.

Three rooms, because three different readers were sharing one. The edition
is for anybody: tonight's read as a picture, the counts under it. Stop press
is the session: a name through its pivot on volume, once. Operations is for
whoever runs this: what failed, which source was short, the draft for X.

Each room is a webhook of its own, and each falls back to the original single
webhook when it has not been given one, so the split costs nothing until the
rooms exist. The server is private, which is the only reason names beyond the
free sample may appear in it; none of this is ever posted anywhere public.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
FALLBACK = "DISCORD_WEBHOOK_URL"
ROOMS = {
    "edition": "DISCORD_WEBHOOK_EDITION",
    "stop_press": "DISCORD_WEBHOOK_STOP_PRESS",
    "ops": "DISCORD_WEBHOOK_OPS",
}
# Discord's edge refuses the default Python-urllib agent with a 403.
AGENT = "base-and-breakout-nightly/1.0"
LIMIT = 1900                      # Discord allows 2,000 characters a message
SESSION_MINUTES = 390             # 9:30 to 16:00 New York
OPEN = dt.time(9, 30)


def hook(room: str) -> str:
    """The webhook for a room, or the shared one, or nothing."""
    return (os.environ.get(ROOMS.get(room, ""), "")
            or os.environ.get(FALLBACK, "") or "").strip()


def same_room(a: str, b: str) -> bool:
    return hook(a) == hook(b)


def post(room: str, content: str = "", *, embeds: list[dict] | None = None,
         username: str | None = None, opener=urllib.request.urlopen) -> bool:
    """Send one message. False when the room has no webhook; raises on refusal."""
    url = hook(room)
    if not url:
        return False
    body: dict = {"content": content[:LIMIT]}
    if embeds:
        body["embeds"] = embeds
    if username:
        body["username"] = username
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": AGENT})
    opener(request, timeout=20)
    return True


def site() -> str:
    return (os.environ.get("SITE_URL") or "https://thetape.cc").rstrip("/")


# ----------------------------------------------------------- the edition

def site_has(session: str, *, wait_seconds: int = 420, pause: int = 20,
             opener=urllib.request.urlopen, sleep=time.sleep) -> bool:
    """Whether the live site has been rebuilt from this session's data yet.

    The picture in the edition post is drawn by the site, and the site is
    rebuilt a minute or two after the data is published. Posting first would
    attach last night's picture to tonight's numbers, and Discord keeps its
    own copy of an image the moment it is posted.
    """
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            request = urllib.request.Request(f"{site()}/api/quotes",
                                             headers={"User-Agent": AGENT})
            with opener(request, timeout=20) as response:
                if json.loads(response.read()).get("as_of") == session:
                    return True
        except Exception:                           # noqa: BLE001
            pass
        if time.monotonic() >= deadline:
            return False
        sleep(pause)


def _weekday(day: str) -> str:
    date = dt.date.fromisoformat(day)
    return f"{date.strftime('%A')} {date.month}/{date.day}"


def edition_message(meta: dict, edition: dict | None, *, behind: int = 0,
                    picture: bool = True) -> tuple[str, list[dict]]:
    """Tonight's read for the edition room: the text, and the card under it."""
    session = meta["as_of"]
    fresh = sum(s["stages"].get("fresh_breakout", 0) for s in meta["screens"])
    # The session date was always here, but as a date you had to remember last
    # night's to interpret. It says so itself.
    stale = (f"  ⚠️ {behind} day(s) behind the last completed session. A market "
             f"holiday looks like this, so does a stuck scan." if behind else "")
    lines = [f"**{_weekday(session)} close**: {meta['universe_count']:,} names "
             f"scanned.{stale}"]
    for screen in meta["screens"]:
        stages = screen["stages"]
        lines.append(f"  {screen['name']}: {screen['total']} "
                     f"({stages.get('fresh_breakout', 0)} fresh, "
                     f"{stages.get('forming', 0)} forming)")
    if fresh == 0:
        lines.append("_Nothing broke out today. That is a reading, not a fault._")

    embeds: list[dict] = []
    if edition:
        in_gear = sum(1 for cell in edition.get("meter") or [] if cell.get("score", 0) > 0)
        cells = len(edition.get("meter") or [])
        embed: dict = {
            "title": f"{edition.get('headline', 'The read')}: {in_gear} of {cells} "
                     f"checks in gear",
            "url": f"{site()}/market/editions/{session}",
            "description": "\n".join(
                [edition.get("blurb") or ""]
                + [f"• {line}" for line in edition.get("checks") or []]).strip()[:1500],
        }
        if picture:
            # The session in the address so Discord cannot serve a kept copy
            # of an earlier night's card.
            embed["image"] = {"url": f"{site()}/share/read.png?v={session}"}
        embeds.append(embed)
    return "\n".join(lines), embeds


def ops_lines(meta: dict) -> list[str]:
    """What whoever runs this needs to know tonight. Empty on a clean night."""
    lines: list[str] = []
    # Heavily traded names that fell out of the universe for want of a share
    # count. Meta, Alphabet and Berkshire all vanished this way and the only
    # trace was a stage count dropping by four out of two thousand.
    lost = meta.get("lost_leaders") or []
    why = meta.get("lost_leader_reasons") or {}
    if lost:
        lines.append("⚠️ Dropped for want of a share count, despite being among "
                     "the most traded names:")
        lines += [f"  {symbol}: {why.get(symbol, 'no reason recorded')}" for symbol in lost]
    fomc = meta.get("fomc") or {}
    if fomc.get("stale"):
        lines.append(f"⚠️ {fomc.get('message', 'The FOMC list needs attention.')}")
    unwell = [s for s in (meta.get("sources") or []) if s.get("status") != "ok"]
    if unwell:
        lines.append("⚠️ Sources not at full strength tonight:")
        lines += [f"  {s['label']} ({s['status']}): {s['detail']}" for s in unwell]
    return lines


# ------------------------------------------------------------ stop press

def volume_pace(quote: dict) -> float | None:
    """Shares so far against an ordinary day's, for the share of the session
    gone by the time of the quote. The same sum the site's own box does."""
    volume, average, at = quote.get("volume"), quote.get("avg_volume"), quote.get("at")
    if not volume or not average or not at:
        return None
    try:
        stamp = dt.datetime.fromisoformat(at)
    except ValueError:
        return None
    minutes = (stamp.hour * 60 + stamp.minute) - (OPEN.hour * 60 + OPEN.minute)
    share = min(1.0, max(0.0, minutes / SESSION_MINUTES))
    # Under a twentieth of the session the sum is mostly the opening cross.
    if share < 0.05:
        return None
    return volume / average / share


def crossings(events, quotes: dict[str, dict], names: dict[str, str], *,
              session: dt.date, already: set[str], min_pace: float = 1.5,
              most: int = 6) -> list[dict]:
    """The crossings worth a post: through the pivot today, on volume, new.

    `events` are the alert sweep's own, so a crossing here and a crossing in a
    subscriber's email are the same judgement. Only long setups, only quotes
    stamped today, only names not already posted this session, and only with
    volume running ahead of an ordinary day: a cross on a quiet tape is the
    one that fails by the close.
    """
    rows = []
    for event in events:
        if event.kind != "crossed" or event.symbol in already:
            continue
        quote = quotes.get(event.symbol) or {}
        if not str(quote.get("at") or "").startswith(session.isoformat()):
            continue
        pace = volume_pace(quote)
        if pace is None or pace < min_pace:
            continue
        rows.append({"symbol": event.symbol, "name": names.get(event.symbol, ""),
                     "screen": event.screen, "pivot": event.pivot,
                     "last": event.last, "above_pct": event.gap_pct, "pace": pace})
    rows.sort(key=lambda row: (-row["pace"], row["symbol"]))
    return rows[:most]


def stop_press_message(rows: list[dict], read_at: str) -> str:
    lines = [f"**Stop press**: delayed prices, read {read_at} ET"]
    for row in rows:
        name = f" {row['name']}" if row["name"] else ""
        lines.append(
            f"`{row['symbol']}`{name}: {row['above_pct']:+.1f}% over its "
            f"{row['pivot']:,.2f} pivot, {row['pace']:.1f}× the usual volume by "
            f"now. {row['screen']}. <{site()}/stocks/{row['symbol']}>")
    lines.append("_A price above a level on a delayed quote, not a close above "
                 "it. Tonight's run decides that._")
    return "\n".join(lines)


# -------------------------------------------------------- the week's wrap

def week_of(day: dt.date) -> tuple[dt.date, dt.date]:
    monday = day - dt.timedelta(days=day.weekday())
    return monday, monday + dt.timedelta(days=4)


def wrap_message(follow: dict, editions: dict, as_of: dt.date) -> str | None:
    """What broke out this week and whether it held. None with nothing to say."""
    monday, friday = week_of(as_of)
    first, last = monday.isoformat(), friday.isoformat()

    seen: dict[tuple[str, str], dict] = {}
    for key, screen in (follow.get("screens") or {}).items():
        for row in screen.get("breakouts") or []:
            if not first <= str(row.get("breakout_date")) <= last:
                continue
            # A name on two screens broke out once.
            seen.setdefault((row["symbol"], row["breakout_date"]),
                            {**row, "screen": screen.get("name", key)})
    rows = list(seen.values())
    days = [e for e in (editions.get("editions") or [])
            if first <= str(e.get("date")) <= last]
    if not rows and not days:
        return None

    lines = [f"**The week on the tape**: {monday.month}/{monday.day} to "
             f"{friday.month}/{friday.day}"]
    if days:
        days.sort(key=lambda e: e["date"])
        lines.append("The read each night: " + " · ".join(
            f"{dt.date.fromisoformat(e['date']).strftime('%a')} {e.get('headline', '?')}"
            for e in days))
        cleared = sum(int(e.get("breakouts") or 0) for e in days)
        failed = sum(int(e.get("failed") or 0) for e in days)
        if cleared or failed:
            lines.append(f"Across the market, {cleared:,} closes through a pivot "
                         f"and {failed:,} tests that fell back.")
    if rows:
        held = [r for r in rows if not r.get("now_below_pivot")]
        median = statistics.median(r["now_pct"] for r in rows)
        lines.append(
            f"On the base screens, {len(rows)} broke out. {len(held)} still sit "
            f"above the pivot at {friday.strftime('%A')}'s close, "
            f"{len(rows) - len(held)} closed back under it. The middle one is "
            f"{median:+.1f}% from its breakout close.")
        ranked = sorted(rows, key=lambda r: -r["now_pct"])

        def line(r: dict) -> str:
            day = dt.date.fromisoformat(r["breakout_date"]).strftime("%a")
            return f"`{r['symbol']}` {r['now_pct']:+.1f}% ({r['screen']}, {day})"

        lines.append("Furthest above: " + ", ".join(line(r) for r in ranked[:3]))
        below = [line(r) for r in ranked[-3:][::-1] if r["now_pct"] < 0]
        if len(ranked) > 3 and below:
            lines.append("Furthest below: " + ", ".join(below))
    else:
        lines.append("Nothing broke out on the base screens this week.")
    lines.append(f"Every breakout and how it went: {site()}/market/followthrough")
    return "\n".join(lines)
