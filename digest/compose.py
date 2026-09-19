"""Turn the published tree into one person's Sunday email.

Everything here reads `out/`, which the nightly already wrote. Nothing in this
module touches the network or the database, so it can be run over a fixture and
read before anything is sent — which is how it should be read the first few
times.

The shape of the email follows the site: the market's condition first, then
what is set up, then what is dated. A quiet week says it is quiet rather than
padding itself out, for the same reason the site does: a week when nothing is
set up is a fact about the market, and dressing it up would make the letter
worth less every time it arrived.

The same letter goes to everyone. Nothing in it is personal -- no watchlist, no
holdings, nothing drawn from an account -- which means the preview one person
reads is exactly what every subscriber receives, and the worst a bug can do is
send the wrong market summary rather than the wrong person's data. Personalised
sections are a later decision with a heavier safety bill; this one is a
newsletter.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
from dataclasses import dataclass, field
from typing import Any

# How many names to list per section. A letter nobody finishes is a letter
# nobody reads, and the site is one tap away for the rest.
MAX_PER_SCREEN = 6
MAX_EVENTS = 8


@dataclass
class Digest:
    """One person's letter, before it is rendered into HTML or text."""
    as_of: str
    verdict: str
    verdict_blurb: str
    checks: list[str] = field(default_factory=list)
    indexes: list[dict] = field(default_factory=list)
    setups: list[dict] = field(default_factory=list)
    week_events: list[dict] = field(default_factory=list)
    quiet: bool = False


def _read(out: pathlib.Path, name: str) -> Any | None:
    try:
        return json.loads((out / name).read_text())
    except (OSError, ValueError):
        return None


def _verdict(breadth: Any, indexes: Any) -> tuple[str, str, list[str]]:
    """The same four checks the home page runs, in words.

    Deliberately a reimplementation of the scoring in web/lib/marketRead.ts
    rather than a second source of truth for the thresholds: the numbers live
    in one place here, and if the two ever disagree the digest is the one that
    is wrong, because the site is what a reader can check.
    """
    cards = {c["key"]: c for c in (breadth or {}).get("cards", [])}
    regime = (indexes or {}).get("regime") or {}
    checks: list[str] = []
    score = 0
    measured = 0

    if regime.get("above") is not None:
        measured += 1
        score += 1 if regime["above"] else -1
        checks.append(regime.get("note") or "")

    b = cards.get("breakouts", {}).get("value")
    f = cards.get("failed_pokes", {}).get("value")
    if b is not None and f is not None and (b > 0 or f > 0):
        measured += 1
        score += -1 if f >= b * 1.5 else (1 if b >= f else 0)
        checks.append(f"{b:.0f} cleared a pivot on the last session, "
                      f"{f:.0f} tested one and fell back.")

    for key, label in (("above_50ma", "above their 50-day line"),
                       ("confirmed_uptrend", "in a confirmed uptrend")):
        card = cards.get(key)
        if not card:
            continue
        measured += 1
        v = card["value"]
        if key == "above_50ma":
            score += 1 if v >= 55 else (-1 if v <= 40 else 0)
        else:
            score += 1 if v >= 40 else (-1 if v <= 25 else 0)
        checks.append(f"{v:.0f}% of the market is {label}.")

    if measured < 2:
        return ("Not enough data to call it",
                "The last run did not publish enough breadth to read the market.",
                checks)

    below_trend = regime.get("above") is False
    if score >= 3 and not below_trend:
        return ("The tape is in gear",
                "Breakouts are being paid for and most of the market is "
                "participating. This is the backdrop these screens are built for.",
                checks)
    if score <= -2:
        return ("The tape is against breakouts",
                "More names are failing at their pivots than holding above them. "
                "Bases that look clean still tend to fail in this.",
                checks)
    if below_trend and score >= 3:
        return ("Mixed, under a falling benchmark",
                "Breadth is holding up, but the benchmark is below its 200-day "
                "line. Those are the weeks that cost the most, because "
                "everything else is telling you to buy.",
                checks)
    return ("Mixed",
            "Some of the market is working and some of it is not. The individual "
            "setup matters more than usual.",
            checks)


def build(out: pathlib.Path) -> Digest:
    """Compose the week's letter. One letter, the same for every subscriber."""
    meta = _read(out, "meta.json") or {}
    breadth = _read(out, "breadth.json")
    indexes = _read(out, "indexes.json")
    releases = _read(out, "catalysts/releases.json") or {}

    verdict, blurb, checks = _verdict(breadth, indexes)

    setups: list[dict] = []
    for screen in meta.get("screens", []):
        key = screen["key"]
        file = _read(out, f"screens/{key}.json") or {}
        fresh = (file.get("setups") or {}).get("fresh_breakout") or []
        forming = (file.get("setups") or {}).get("forming") or []
        rows = [
            {"symbol": s["symbol"], "name": s["name"], "stage": s["stage"],
             "rs": s.get("rs_rating"), "pivot": s.get("pivot"),
             "close": s.get("close")}
            for s in (fresh + forming)[:MAX_PER_SCREEN]
        ]
        if rows:
            setups.append({"screen": screen["name"], "key": key, "rows": rows,
                           "total": screen.get("total", 0)})

    week_events = [
        r for r in (releases.get("releases") or [])
        if r.get("notable") and 0 <= r.get("days_until", 99) <= 9
    ][:MAX_EVENTS]
    for meeting in (releases.get("fomc") or {}).get("meetings", []):
        if 0 <= meeting.get("days_until", 99) <= 9:
            week_events.insert(0, {"date": meeting["date"],
                                   "name": meeting.get("label", "FOMC decision"),
                                   "notable": True})

    quiet = not setups and not week_events

    return Digest(
        as_of=meta.get("as_of", ""),
        verdict=verdict,
        verdict_blurb=blurb,
        checks=[c for c in checks if c],
        indexes=(indexes or {}).get("rows", []),
        setups=setups,
        week_events=week_events,
        quiet=quiet,
    )


def subject(d: Digest) -> str:
    """What lands in the inbox list, where only the first few words show."""
    if d.quiet:
        return "The week ahead: a quiet one"
    head = d.verdict.replace("The tape is ", "").capitalize()
    total = sum(len(s["rows"]) for s in d.setups)
    return f"The week ahead: {head}, {total} set up"
