"""Watchlist alerts: an email when a stock a subscriber starred reaches its pivot.

Runs inside the intraday quotes job, every fifteen minutes during the session.
That job already holds what this needs: every screen's full setup list (public
and gated) with each pivot, and a delayed price for the names on them.

Three events, for setups still forming:

  * crossed  a long setup traded through its pivot.
  * near     a long setup within NEAR_PCT under its pivot.
  * broke    a short setup (a breakdown screen) traded through its level.

Who gets them: people with watchlist alerts switched on in settings, not
unsubscribed, and with a live subscription. Subscribers only, because the
pivot of a name outside the free sample is part of what is paid for, and an
email is a place the paywall cannot reach.

What is guarded, in the same spirit as the weekly digest:

  * Each (person, stock, event, session) is sent at most once. The rows are
    claimed in watchlist_alert_log with "ignore duplicates" before anything is
    sent, and only the rows that came back new are sent. A failed send gives
    its rows back so the next run tries again.
  * Nothing goes out outside the regular session. Before the open the delayed
    price is yesterday's close, and "near its pivot" on that is old news.
  * No address is printed. Recipients are numbered, and Resend's error text has
    the address scrubbed, because the Actions log is public.
  * One refused message does not stop the rest.
"""
from __future__ import annotations

import datetime as dt
import html as htmlmod
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

from digest.send import (DigestError, PAUSE_BETWEEN_SENDS, _supabase_headers,
                         deliver)

NEW_YORK = ZoneInfo("America/New_York")
# Close enough to be worth looking at, far enough that it is not the same thing
# as crossing. Under a percent and a half is a day's ordinary range for most of
# what these screens hold.
NEAR_PCT = 1.5
OPEN, CLOSE = dt.time(9, 30), dt.time(16, 0)
KEEP_DAYS = 30
KIND_ORDER = {"crossed": 0, "broke": 1, "near": 2}


@dataclass(frozen=True)
class Event:
    symbol: str
    kind: str
    screen: str
    pivot: float
    last: float

    @property
    def gap_pct(self) -> float:
        return 100.0 * (self.last / self.pivot - 1.0)


# ------------------------------------------------------------------ who

def is_subscriber(row: dict[str, Any], now: dt.datetime) -> bool:
    """The same rule as public.is_subscriber() in supabase/paywall.sql."""
    if row.get("comped"):
        return True
    if row.get("status") not in ("trialing", "active", "past_due"):
        return False
    end = row.get("current_period_end")
    if not end:
        return True
    try:
        when = dt.datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return False
    return when > now


def _get(url: str, key: str, table: str, params: dict[str, str]) -> list[dict]:
    resp = requests.get(f"{url}/rest/v1/{table}", headers=_supabase_headers(key),
                        params=params, timeout=30)
    if resp.status_code != 200:
        raise DigestError(f"reading {table} failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def fetch_watchers(url: str, key: str,
                   now: dt.datetime | None = None) -> dict[str, dict[str, Any]]:
    """{user_id: {email, token, symbols}} for subscribers who asked for alerts."""
    now = now or dt.datetime.now(dt.timezone.utc)
    prefs = _get(url, key, "email_prefs", {
        "select": "user_id,email,unsubscribe_token",
        "watchlist_alerts": "eq.true",
        "disabled_at": "is.null",
    })
    if not prefs:
        return {}
    subs = _get(url, key, "subscriptions", {
        "select": "user_id,status,current_period_end,comped"})
    paying = {row["user_id"] for row in subs if is_subscriber(row, now)}
    people = {row["user_id"]: {"email": row["email"],
                               "token": row["unsubscribe_token"],
                               "symbols": set()}
              for row in prefs if row["user_id"] in paying and row.get("email")}
    if not people:
        return {}
    for row in _get(url, key, "watchlist", {"select": "user_id,symbol"}):
        person = people.get(row["user_id"])
        if person is not None:
            person["symbols"].add(str(row["symbol"]).upper())
    return {uid: p for uid, p in people.items() if p["symbols"]}


def watched_symbols() -> set[str]:
    """Every symbol on an alerting subscriber's list, or nothing on any error.

    For the quote sweep's ordering only: a name somebody is waiting on should
    not be the one the 400-name budget runs out before.
    """
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        return set()
    try:
        watchers = fetch_watchers(url, key)
    except (DigestError, requests.RequestException):
        return set()
    return set().union(*(p["symbols"] for p in watchers.values())) if watchers else set()


# ------------------------------------------------------------------ what

def forming_levels(screens: Iterable[dict]) -> dict[str, list[dict]]:
    """Every forming setup's level, by symbol: {symbol: [{screen, pivot, short}]}."""
    levels: dict[str, list[dict]] = {}
    for payload in screens:
        short = payload.get("direction") == "short"
        name = payload.get("name") or payload.get("screen") or ""
        for row in (payload.get("setups") or {}).get("forming") or []:
            symbol, pivot = row.get("symbol"), row.get("pivot")
            if not symbol or not isinstance(pivot, (int, float)) or pivot <= 0:
                continue
            levels.setdefault(symbol, []).append(
                {"screen": name, "pivot": float(pivot), "short": short})
    return levels


def detect(levels: dict[str, list[dict]], quotes: dict[str, dict],
           symbols: Iterable[str]) -> list[Event]:
    """Events for the given symbols, one per (symbol, kind), strongest first."""
    found: dict[tuple[str, str], Event] = {}
    for symbol in symbols:
        quote = quotes.get(symbol) or {}
        last = quote.get("last")
        if not isinstance(last, (int, float)) or last <= 0:
            continue
        for level in levels.get(symbol, []):
            pivot = level["pivot"]
            if level["short"]:
                kind = "broke" if last <= pivot else None
            elif last >= pivot:
                kind = "crossed"
            elif 100.0 * (1.0 - last / pivot) <= NEAR_PCT:
                kind = "near"
            else:
                kind = None
            if kind and (symbol, kind) not in found:
                found[(symbol, kind)] = Event(symbol, kind, level["screen"], pivot, float(last))
    # A stock through its pivot is not also "near" it on another screen's level.
    crossed = {s for (s, k) in found if k == "crossed"}
    events = [e for (s, k), e in found.items() if not (k == "near" and s in crossed)]
    return sorted(events, key=lambda e: (KIND_ORDER[e.kind], e.symbol))


def in_session(now: dt.datetime) -> bool:
    local = now.astimezone(NEW_YORK)
    return local.weekday() < 5 and OPEN <= local.time() < CLOSE


# ------------------------------------------------------------------ record

def claim(url: str, key: str, rows: list[dict]) -> list[dict]:
    """Insert, skipping rows already there. Returns only the rows that were new."""
    if not rows:
        return []
    resp = requests.post(
        f"{url}/rest/v1/watchlist_alert_log",
        headers={**_supabase_headers(key),
                 "Prefer": "resolution=ignore-duplicates,return=representation"},
        params={"on_conflict": "user_id,symbol,kind,session"},
        json=rows, timeout=30)
    if resp.status_code not in (200, 201):
        raise DigestError(f"recording alerts failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def release(url: str, key: str, user_id: str, rows: list[dict]) -> None:
    """Give claimed rows back after a failed send, so the next run retries them."""
    for row in rows:
        requests.delete(
            f"{url}/rest/v1/watchlist_alert_log", headers=_supabase_headers(key),
            params={"user_id": f"eq.{user_id}", "symbol": f"eq.{row['symbol']}",
                    "kind": f"eq.{row['kind']}", "session": f"eq.{row['session']}"},
            timeout=30)


def prune(url: str, key: str, today: dt.date) -> None:
    cutoff = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    requests.delete(f"{url}/rest/v1/watchlist_alert_log",
                    headers=_supabase_headers(key),
                    params={"session": f"lt.{cutoff}"}, timeout=30)


# ------------------------------------------------------------------ the letter

def _line(e: Event) -> str:
    if e.kind == "crossed":
        return (f"{e.symbol} crossed its pivot of ${e.pivot:,.2f} ({e.screen}): "
                f"last ${e.last:,.2f}, {e.gap_pct:+.1f}%.")
    if e.kind == "broke":
        return (f"{e.symbol} broke below its level of ${e.pivot:,.2f} ({e.screen}): "
                f"last ${e.last:,.2f}, {e.gap_pct:+.1f}%.")
    return (f"{e.symbol} is {abs(e.gap_pct):.1f}% under its pivot of ${e.pivot:,.2f} "
            f"({e.screen}): last ${e.last:,.2f}.")


def subject(events: list[Event]) -> str:
    if len(events) == 1:
        e = events[0]
        return {"crossed": f"{e.symbol} crossed its pivot",
                "broke": f"{e.symbol} broke its level",
                "near": f"{e.symbol} is near its pivot"}[e.kind]
    names = ", ".join(e.symbol for e in events[:3])
    more = f" and {len(events) - 3} more" if len(events) > 3 else ""
    return f"Watchlist: {names}{more}"


def render(events: list[Event], site: str, unsubscribe: str,
           stamp: str) -> tuple[str, str]:
    """(html, text). Plain on purpose: it is read on a phone in a hurry."""
    settings_url = f"{site}/settings"
    text_lines = [_line(e) + f"\n  {site}/stocks/{e.symbol}" for e in events]
    text = ("\n\n".join(text_lines)
            + f"\n\nDelayed quotes as of {stamp} ET. A screen match is a shape, "
              "not a prediction, and not investment advice."
            + f"\n\nTurn these off: {settings_url}\nUnsubscribe from all email: {unsubscribe}\n")
    items = "".join(
        f'<li style="margin:0 0 12px"><a href="{site}/stocks/{e.symbol}" '
        f'style="color:#1a56db;font-weight:600;text-decoration:none">{e.symbol}</a> '
        f"{htmlmod.escape(_line(e)[len(e.symbol) + 1:])}</li>"
        for e in events)
    html = (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
        'font-size:15px;line-height:1.5;color:#111;max-width:560px">'
        f'<ul style="padding-left:18px;margin:0 0 16px">{items}</ul>'
        f'<p style="color:#555;font-size:13px">Delayed quotes as of {stamp} ET. '
        "A screen match is a shape, not a prediction, and not investment advice.</p>"
        f'<p style="color:#555;font-size:13px"><a href="{settings_url}">Turn these off</a>'
        f' · <a href="{unsubscribe}">Unsubscribe from all email</a></p></div>')
    return html, text


# ------------------------------------------------------------------ run

def run(screens: list[dict], quotes: dict[str, dict], *, send: bool,
        now: dt.datetime | None = None, notice=print) -> int:
    """Check every watcher's list against the latest quotes. Returns failures."""
    now = now or dt.datetime.now(dt.timezone.utc)
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        notice("alerts: Supabase is not configured; skipped.")
        return 0
    if not in_session(now):
        notice("alerts: outside the regular session; nothing sent.")
        return 0

    watchers = fetch_watchers(url, key, now)
    levels = forming_levels(screens)
    session = now.astimezone(NEW_YORK).date()
    stamp = now.astimezone(NEW_YORK).strftime("%-I:%M %p")
    site = os.environ.get("SITE_URL", "https://thetape.cc").rstrip("/")
    sender = os.environ.get("DIGEST_FROM", "The Tape <noreply@thetape.cc>")
    api_key = os.environ.get("RESEND_API_KEY") or ""
    if send and not api_key:
        notice("alerts: RESEND_API_KEY is not set; nothing sent.")
        return 0

    total = len(watchers)
    sent = failed = quiet = 0
    for n, (user_id, person) in enumerate(watchers.items(), 1):
        who = f"recipient {n}/{total}"
        events = detect(levels, quotes, person["symbols"])
        if not events:
            quiet += 1
            continue
        if not send:
            notice(f"  {who}: would send {len(events)} alert(s)")
            continue
        wanted = [{"user_id": user_id, "symbol": e.symbol, "kind": e.kind,
                   "session": session.isoformat(), "screen": e.screen}
                  for e in events]
        fresh = {(r["symbol"], r["kind"]) for r in claim(url, key, wanted)}
        events = [e for e in events if (e.symbol, e.kind) in fresh]
        if not events:
            quiet += 1
            continue
        unsubscribe = f"{site}/unsubscribe?t={person['token']}"
        html, text = render(events, site, unsubscribe, stamp)
        try:
            deliver(api_key, sender, person["email"], subject(events), html, text,
                    unsubscribe)
        except (DigestError, requests.RequestException) as exc:
            failed += 1
            release(url, key, user_id, [r for r in wanted
                                        if (r["symbol"], r["kind"]) in fresh])
            notice(f"  {who}: NOT sent — {str(exc).replace(person['email'], '<address>')}")
            continue
        sent += 1
        notice(f"  {who}: sent {len(events)} alert(s)")
        time.sleep(PAUSE_BETWEEN_SENDS)

    if send:
        prune(url, key, session)
    notice(f"alerts: {total} watcher(s), {sent} emailed, {quiet} with nothing new, "
           f"{failed} failed")
    return failed
