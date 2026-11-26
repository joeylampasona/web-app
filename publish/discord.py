"""What goes to Discord, and to which room.

Four rooms, because four different readers were sharing one. The edition is
for anybody: tonight's read as a picture, the counts under it, what is new on
a screen and what the morning holds. Stop press is the session: a name
through its pivot on volume, once, and how those names closed. Earnings is
the read on each company that has just reported. Operations is for whoever
runs this: what failed, which source was short, the draft for X.

Each room is a webhook of its own, and each falls back to the original single
webhook when it has not been given one, so the split costs nothing until the
rooms exist. The server is private, which is the only reason names beyond the
free sample may appear in it; none of this is ever posted anywhere public.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
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
    "earnings": "DISCORD_WEBHOOK_EARNINGS",
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
                rebuilt = json.loads(response.read()).get("as_of") == session
            if rebuilt:
                # And the picture itself answers. A card that will not draw
                # is a post without a picture, not a post with a broken one.
                picture = urllib.request.Request(read_card(session),
                                                 headers={"User-Agent": AGENT})
                with opener(picture, timeout=30) as response:
                    response.read()
                return True
        except Exception:                           # noqa: BLE001
            pass
        if time.monotonic() >= deadline:
            return False
        sleep(pause)


def read_card(session: str) -> str:
    """Where the site draws tonight's read. The session is in the address so
    that Discord cannot serve a kept copy of an earlier night's card."""
    return f"{site()}/share/read.png?v={session}"


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
            embed["image"] = {"url": read_card(session)}
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


# -------------------------------------------------- new on a screen

NAMES_A_SCREEN = 14


def new_on_screens(diff: dict, meta: dict) -> str | None:
    """The names that started forming last night, by screen. None if none."""
    labels = {s["key"]: s["name"] for s in meta.get("screens") or []}
    lines: list[str] = []
    for key, row in (diff.get("screens") or {}).items():
        fresh = list(row.get("newly_forming") or [])
        if not fresh:
            continue
        shown = ", ".join(f"`{symbol}`" for symbol in fresh[:NAMES_A_SCREEN])
        more = f" and {len(fresh) - NAMES_A_SCREEN} more" if len(fresh) > NAMES_A_SCREEN else ""
        lines.append(f"  {labels.get(key, key)}: {shown}{more}")
    if not lines:
        return None
    return "\n".join(["**New on a screen**: started forming a base last night"]
                     + lines + [f"<{site()}/screens>"])


# ------------------------------------------------------ the morning line

def next_session(day: dt.date) -> dt.date:
    """The next weekday. Market holidays are not known here, so on one the
    line is for a day that does not trade, and says a date either way."""
    nxt = day + dt.timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += dt.timedelta(days=1)
    return nxt


def morning_line(upcoming: dict, releases: dict, on_screen: dict[str, str],
                 as_of: dt.date, most: int = 18) -> str | None:
    """Who on a screen reports next session, and what data is due. None when
    there is neither: a line that says nothing every morning gets muted."""
    day = next_session(as_of)
    stamp = day.isoformat()
    reporting = sorted({e["ticker"] for e in upcoming.get("events") or []
                        if e.get("type") == "earnings" and e.get("date") == stamp
                        and not e.get("readthrough")})
    ours = [s for s in reporting if s in on_screen]
    due = [r["name"] for r in releases.get("releases") or []
           if r.get("date") == stamp and r.get("notable")]
    fomc = [m.get("label", "FOMC decision")
            for m in (releases.get("fomc") or {}).get("meetings") or []
            if m.get("date") == stamp]
    if not ours and not due and not fomc:
        return None

    lines = [f"**The morning line**: {day.strftime('%A')} {day.month}/{day.day}"]
    if ours:
        shown = ", ".join(f"`{s}` ({on_screen[s]})" for s in ours[:most])
        more = f" and {len(ours) - most} more" if len(ours) > most else ""
        lines.append(f"Reporting, and on a screen: {shown}{more}")
    if reporting:
        others = len(reporting) - len(ours)
        if ours and others:
            lines.append(f"{others:,} more in the universe report the same day.")
        elif not ours:
            lines.append(f"{len(reporting):,} in the universe report; none of them "
                         f"is on a screen.")
    if fomc or due:
        lines.append("Data due: " + "; ".join(fomc + due[:8]))
    lines.append(f"<{site()}/market/calendar>")
    return "\n".join(lines)


# ------------------------------------------------------- earnings reads

READS_A_NIGHT = 6
READ_WINDOW_DAYS = 14
READ_MEMORY_DAYS = 45


def reads_to_post(reads: list[dict], on_screen: dict[str, str], as_of: dt.date,
                  posted: dict[str, str]) -> list[dict]:
    """Tonight's reads for the earnings room: reported in the last fortnight,
    the filing for that report in hand, and not posted before; names on a
    screen first.

    Only a read that covers the quarter just reported. A read is built from
    the 10-Q, which is filed days after the print, and until it is the read
    on file is of the quarter before. The first cards this room was sent
    included three of those under the date of the new report, which says the
    opposite of what it should. They wait for the filing now, which is why
    the window is a fortnight and not a few days.
    """
    cutoff = (as_of - dt.timedelta(days=READ_WINDOW_DAYS)).isoformat()
    fresh = [r for r in reads
             if r.get("symbol") and str(r.get("report_date") or "") >= cutoff
             and r.get("covers") is True
             and posted.get(r["symbol"]) != r.get("report_date")]
    # Newest report first, then whether it is on a screen. Stable, so the
    # file's own order decides the rest.
    fresh.sort(key=lambda r: r["report_date"], reverse=True)
    fresh.sort(key=lambda r: r["symbol"] not in on_screen)
    return fresh[:READS_A_NIGHT]


_SHARE_CLASS = re.compile(
    r"[\s,]+(Class [A-Z]\s+)?(Common Stock|Common Shares|Ordinary Shares|"
    r"American Depositary Shares.*)$", re.IGNORECASE)


def company_name(listed: str) -> str:
    """A company's name without the description of its share class."""
    return _SHARE_CLASS.sub("", listed.split(", Inc")[0] if listed.endswith(", Inc.") else listed).strip()


def read_embed(read: dict, on_screen: dict[str, str]) -> dict:
    """One company's read as a card: the takeaway, the figures, the question."""
    symbol = read["symbol"]
    lines = [f"• {flag['text']}" for flag in (read.get("flags") or [])[:5]
             if flag.get("text")]
    verdict = read.get("verdict") or {}
    if verdict.get("growth") or verdict.get("proof"):
        lines.append(f"Growth {str(verdict.get('growth', '?')).lower()}, "
                     f"proof {str(verdict.get('proof', '?')).lower()}.")
    if verdict.get("question"):
        lines.append(verdict["question"])
    if read.get("test"):
        lines.append(read["test"])
    reported = dt.date.fromisoformat(read["report_date"])
    foot = f"Reported {reported.month}/{reported.day}"
    try:
        ended = dt.date.fromisoformat(str((read.get("glance") or {}).get("end")))
        foot += f" · quarter ended {ended.month}/{ended.day}"
    except ValueError:
        pass
    if symbol in on_screen:
        foot += f" · on {on_screen[symbol]}"
    name = company_name(str(read.get("name") or ""))
    return {
        "title": (f"{symbol} {name}: {read.get('takeaway') or 'the read'}")[:250],
        "url": f"{site()}/stocks/{symbol}",
        "description": "\n".join(lines)[:1500],
        "footer": {"text": foot},
    }


def remember_reads(posted: dict[str, str], rows: list[dict], as_of: dt.date) -> dict[str, str]:
    """The note of what has been posted, with tonight's added and the old dropped."""
    cutoff = (as_of - dt.timedelta(days=READ_MEMORY_DAYS)).isoformat()
    kept = {symbol: day for symbol, day in posted.items() if str(day) >= cutoff}
    kept.update({row["symbol"]: row["report_date"] for row in rows})
    return kept


# -------------------------------------------- who reported, and the reaction

BELL_OPEN, BELL_CLOSE = dt.time(9, 30), dt.time(16, 0)
#: The two windows a run may post in, New York time. Outside them a run says
#: nothing: a "before the open" post that arrives at eleven is wrong twice.
PRE_WINDOW = (dt.time(8, 30), dt.time(9, 30))
POST_WINDOW = (dt.time(17, 30), dt.time(20, 30))
#: How many companies a run looks up one at a time, and names.
REPORTERS_NAMED = 30


def which_run(now: dt.datetime) -> str | None:
    """"pre", "post" or None, from the New York clock on a weekday."""
    local = now.astimezone(NEW_YORK)
    if local.weekday() >= 5:
        return None
    clock = local.time()
    if PRE_WINDOW[0] <= clock < PRE_WINDOW[1]:
        return "pre"
    if POST_WINDOW[0] <= clock < POST_WINDOW[1]:
        return "post"
    return None


def reporters_to_name(symbols: list[str], quotes: dict[str, dict],
                      on_screen: dict[str, str], already: set[str]) -> list[str]:
    """Who to look up and name: not yet posted, names on a screen first, then
    the largest companies."""
    fresh = [s for s in dict.fromkeys(symbols) if s not in already]
    fresh.sort(key=lambda s: -((quotes.get(s) or {}).get("market_cap") or 0.0))
    fresh.sort(key=lambda s: s not in on_screen)
    return fresh[:REPORTERS_NAMED]


def implied_moves(earnings: dict) -> dict[str, float]:
    """What the options priced for each coming report, as a percentage move
    either way: {ticker: pct}. From the earnings file's own table; a company
    not in it has no figure, which is most of them."""
    out: dict[str, float] = {}
    rows = sorted((earnings.get("priced") or {}).get("upcoming") or [],
                  key=lambda row: str(row.get("report_date") or ""))
    for row in rows:
        if row.get("stale"):
            # Read too long before the report to be called what the options
            # priced. No figure is better than a week-old one in a line that
            # sets the move beside it.
            continue
        try:
            pct = float(row.get("implied_pct"))
        except (TypeError, ValueError):
            continue
        if row.get("ticker") and pct > 0:
            out[row["ticker"]] = pct
    return out


def reporter_rows(run: str, named: list[str], quotes: dict[str, dict],
                  tables: dict[str, dict | None], on_screen: dict[str, str],
                  implied: dict[str, float] | None = None) -> list[dict]:
    """The lines for one run. Before the open: the companies set to report
    before the bell. After the close: everybody else due today."""
    rows = []
    for symbol in named:
        table = tables.get(symbol)
        if not table:
            continue                     # no line for today: not reporting, or unknown
        early = table["hour"] < BELL_OPEN
        late = table["hour"] >= BELL_CLOSE
        if run == "pre" and not early:
            continue
        quote = quotes.get(symbol) or {}
        if run == "pre":
            move, when = quote.get("pre_pct"), "before the bell"
        elif late:
            move, when = quote.get("post_pct"), "after the bell"
        else:
            # Reported in the morning or mid-session and not caught earlier:
            # the session's own move is the reaction.
            move, when = quote.get("session_pct"), "on the day"
        rows.append({"symbol": symbol, "name": company_name(quote.get("name") or ""),
                     "move": move, "when": when, "screen": on_screen.get(symbol),
                     "implied": (implied or {}).get(symbol),
                     "eps": table.get("eps"), "estimate": table.get("estimate"),
                     "surprise_pct": table.get("surprise_pct"),
                     "revenue": table.get("revenue"),
                     "revenue_estimate": table.get("revenue_estimate"),
                     "revenue_surprise_pct": table.get("revenue_surprise_pct")})
    return rows


def money(amount: float) -> str:
    """Revenue the way a headline writes it: $4.21bn, $812m."""
    if abs(amount) >= 1e9:
        return f"${amount / 1e9:,.2f}bn"
    if abs(amount) >= 1e6:
        return f"${amount / 1e6:,.0f}m"
    return f"${amount:,.0f}"


def reporters_message(run: str, rows: list[dict], day: dt.date, read_at: str,
                      others: int = 0) -> str | None:
    if not rows:
        return None
    head = "Reported before the open" if run == "pre" else "Reported after the close"
    lines = [f"**{head}**: {day.strftime('%A')} {day.month}/{day.day}, "
             f"prices read {read_at} ET"]
    for row in rows:
        parts = []
        # The move beside what the options had priced, so a reader can see at
        # once whether it was a surprise: 6% is a shrug against 12% and a
        # shock against 3%.
        priced = (f"options priced ±{row['implied']:.1f}%"
                  if row.get("implied") else None)
        if row["move"] is not None:
            parts.append(f"{row['move']:+.1f}% {row['when']}"
                         + (f", {priced}" if priced else ""))
        elif priced:
            parts.append(priced)
        if row["eps"] is not None and row["estimate"] is not None:
            beat = (f" ({row['surprise_pct']:+.1f}%)"
                    if row["surprise_pct"] is not None else "")
            parts.append(f"EPS {row['eps']:.2f} against {row['estimate']:.2f} expected{beat}")
        elif row["eps"] is not None:
            parts.append(f"EPS {row['eps']:.2f}")
        else:
            parts.append("EPS not in yet")
        if row.get("revenue") and row.get("revenue_estimate"):
            beat = (f" ({row['revenue_surprise_pct']:+.1f}%)"
                    if row.get("revenue_surprise_pct") is not None else "")
            parts.append(f"revenue {money(row['revenue'])} against "
                         f"{money(row['revenue_estimate'])}{beat}")
        elif row.get("revenue"):
            parts.append(f"revenue {money(row['revenue'])}")
        if row["screen"]:
            parts.append(f"on {row['screen']}")
        name = f" {row['name']}" if row["name"] else ""
        lines.append(f"`{row['symbol']}`{name}: " + " · ".join(parts))
    if others > 0:
        lines.append(f"{others:,} more in the universe are due today and were not looked up.")
    lines.append("_Delayed prices. The read on each follows here once its 10-Q is filed._")
    return "\n".join(lines)


# ------------------------------------------------- the week's earnings

def coming_week(today: dt.date) -> tuple[dt.date, dt.date]:
    """Monday to Friday of the week to come: next week on a weekend, this
    week on a weekday."""
    if today.weekday() >= 5:
        monday = today + dt.timedelta(days=7 - today.weekday())
    else:
        monday = today - dt.timedelta(days=today.weekday())
    return monday, monday + dt.timedelta(days=4)


def week_ahead_message(upcoming: dict, on_screen: dict[str, str],
                       implied: dict[str, float], today: dt.date,
                       most: int = 14) -> str | None:
    """Who on a screen reports each day of the week to come. None when nobody
    in the universe reports at all."""
    monday, friday = coming_week(today)
    # One day a company. The calendar can carry a confirmed date and an
    # older tentative one for the same report, and the first run of this
    # listed three companies on two days each. A confirmed date wins; with
    # none confirmed, the earliest.
    chosen: dict[str, tuple[bool, str]] = {}
    for event in upcoming.get("events") or []:
        if event.get("type") != "earnings" or event.get("readthrough"):
            continue
        day = str(event.get("date"))
        if not monday.isoformat() <= day <= friday.isoformat():
            continue
        rank = (event.get("confirmed") != "confirmed", day)
        if event["ticker"] not in chosen or rank < chosen[event["ticker"]]:
            chosen[event["ticker"]] = rank
    by_day: dict[str, set[str]] = {}
    for ticker, (_, day) in chosen.items():
        by_day.setdefault(day, set()).add(ticker)
    if not by_day:
        return None

    lines = [f"**The week's earnings**: {monday.month}/{monday.day} to "
             f"{friday.month}/{friday.day}, the names on a screen"]
    for offset in range(5):
        day = monday + dt.timedelta(days=offset)
        due = by_day.get(day.isoformat()) or set()
        if not due:
            continue
        ours = sorted(s for s in due if s in on_screen)
        label = f"{day.strftime('%a')} {day.month}/{day.day}"

        def one(symbol: str) -> str:
            priced = f" ±{implied[symbol]:.0f}%" if symbol in implied else ""
            return f"`{symbol}` ({on_screen[symbol]}){priced}"

        others = len(due) - len(ours)
        if ours:
            shown = ", ".join(one(s) for s in ours[:most])
            more = f" and {len(ours) - most} more" if len(ours) > most else ""
            rest = f" · {others} more in the universe" if others else ""
            lines.append(f"{label}: {shown}{more}{rest}")
        else:
            lines.append(f"{label}: none on a screen · {others} in the universe")
    if any(s in implied for due in by_day.values() for s in due if s in on_screen):
        lines.append("_± is the move the options price for the report._")
    lines.append(f"<{site()}/market/calendar>")
    return "\n".join(lines)


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


def settled_message(posted: dict[str, dict], quotes: dict[str, dict],
                    day: dt.date, read_at: str) -> str | None:
    """How the day's stop press names stood after the bell. None with no
    price for any of them."""
    held, fell = [], []
    for symbol, row in sorted(posted.items()):
        quote = quotes.get(symbol) or {}
        last, pivot = quote.get("last"), row.get("pivot")
        if not last or not pivot or not str(quote.get("at") or "").startswith(day.isoformat()):
            continue
        gap = 100.0 * (last / pivot - 1.0)
        text = f"`{symbol}` {gap:+.1f}% against {pivot:,.2f}"
        (held if last >= pivot else fell).append((gap, text))
    if not held and not fell:
        return None
    total = len(held) + len(fell)
    lines = [f"**Stop press, settled**: {day.strftime('%A')}'s {total} "
             f"name{'s' if total != 1 else ''} after the bell"]
    if held:
        lines.append(f"Held above the pivot ({len(held)}): "
                     + ", ".join(text for _, text in sorted(held, reverse=True)))
    if fell:
        lines.append(f"Fell back under it ({len(fell)}): "
                     + ", ".join(text for _, text in sorted(fell)))
    lines.append(f"_Delayed prices read {read_at} ET. Tonight's run has the "
                 f"settled closes._")
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

        # Not "furthest above" in a week when nothing is above.
        best = "Furthest above" if ranked[0]["now_pct"] > 0 else "Holding up best"
        lines.append(f"{best}: " + ", ".join(line(r) for r in ranked[:3]))
        below = [line(r) for r in ranked[-3:][::-1] if r["now_pct"] < 0]
        if len(ranked) > 3 and below:
            lines.append("Furthest below: " + ", ".join(below))
    else:
        lines.append("Nothing broke out on the base screens this week.")
    lines.append(f"Every breakout and how it went: {site()}/market/followthrough")
    return "\n".join(lines)
