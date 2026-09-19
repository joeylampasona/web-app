"""Render a Digest as HTML and as plain text.

Both, always. A text part is not a courtesy: a message with only an HTML body
scores worse with spam filters, and the sign-in codes share this domain, so a
digest that lands in spam eventually takes the auth mail down with it.

Every value that reaches the HTML goes through esc(). None of this is
user-supplied today, but a company name with an ampersand in it is enough to
produce markup a client renders wrong, and the failure would look like a
styling bug rather than an escaping one.

Colours are literal hex. Email clients ignore CSS variables and mostly ignore
<style> blocks, so the design tokens are transcribed here rather than imported;
the comment beside them says which token each one is, so a change to the
palette can be followed through to this file.
"""
from __future__ import annotations

import datetime as dt
from html import escape as esc

from digest.compose import Digest

BG      = "#0C0D12"   # --surface-0
CARD    = "#12131A"   # --surface-1
RAISED  = "#1A1C25"   # --surface-2
INK     = "#FAF9F6"   # --text-primary
MUTED   = "#A8AAB8"   # --text-secondary
DIM     = "#6E7180"   # --text-muted
BORDER  = "#24262F"   # --border
BRAND   = "#DAFC4F"   # --brand
ONBRAND = "#14200A"   # --on-brand
GAIN    = "#16A34A"   # --gain
LOSS    = "#DC2626"   # --loss
WARN    = "#EAB308"   # --warn

FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif")
MONO = "'SF Mono',Menlo,Consolas,monospace"


def _day(iso: str) -> str:
    try:
        return dt.date.fromisoformat(iso).strftime("%a %-d %b")
    except (ValueError, TypeError):
        return iso or ""


def text(d: Digest, site: str, unsubscribe_url: str) -> str:
    """The plain-text part. Written to be read, not as a fallback nobody sees."""
    lines = [f"THE TAPE — the week ahead", f"Measured at the {d.as_of} close.", ""]
    lines += [d.verdict.upper(), d.verdict_blurb, ""]
    for c in d.checks:
        lines.append(f"  - {c}")
    if d.indexes:
        lines.append("")
        for row in d.indexes:
            side = ("above" if row.get("above_200") else "below") \
                if row.get("above_200") is not None else "—"
            lines.append(f"  {row['symbol']}  {row['close']}  ({side} its 200-day)")

    if d.watchlist_breakouts:
        lines += ["", "ON YOUR WATCHLIST — broke out",
                  "  " + ", ".join(r["symbol"] for r in d.watchlist_breakouts)]
    if d.watchlist_events:
        lines += ["", "ON YOUR WATCHLIST — dated this week"]
        for e in d.watchlist_events:
            lines.append(f"  {_day(e['date'])}  {e['ticker']}  {e.get('type_label', e.get('type',''))}")

    if d.setups:
        lines += ["", "SET UP"]
        for s in d.setups:
            names = ", ".join(r["symbol"] for r in s["rows"])
            lines.append(f"  {s['screen']} ({s['total']}): {names}")

    if d.week_events:
        lines += ["", "DATED THIS WEEK"]
        for e in d.week_events:
            lines.append(f"  {_day(e['date'])}  {e['name']}")

    if d.quiet:
        lines += ["", "Nothing is set up and nothing is dated. A quiet week is a",
                  "quiet week — there is no reading hidden in it."]

    lines += ["", "—",
              "A screening and market-analytics tool. Not investment advice.",
              "We are not a registered investment adviser.",
              f"Open the site: {site}",
              f"Stop these emails: {unsubscribe_url}"]
    return "\n".join(lines)


def _section(title: str, body: str) -> str:
    return (
        f'<tr><td style="padding:0 28px 6px 28px;font-family:{FONT};">'
        f'<p style="margin:22px 0 10px 0;font-size:12px;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:{DIM};font-weight:600;">{esc(title)}</p>'
        f'{body}</td></tr>'
    )


def _row(left: str, right: str = "") -> str:
    return (
        f'<p style="margin:0 0 6px 0;font-size:14px;line-height:1.5;color:{INK};">'
        f'{left}'
        + (f'<span style="color:{MUTED};"> {right}</span>' if right else "")
        + '</p>'
    )


def html(d: Digest, site: str, unsubscribe_url: str) -> str:
    parts: list[str] = []

    checks = "".join(
        f'<p style="margin:0 0 5px 0;font-size:13px;line-height:1.5;color:{MUTED};">'
        f'&middot; {esc(c)}</p>' for c in d.checks)
    parts.append(
        f'<tr><td style="padding:28px 28px 4px 28px;font-family:{FONT};">'
        f'<p style="margin:0;font-size:12px;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:{BRAND};font-weight:600;">The Tape</p>'
        f'<h1 style="margin:12px 0 0 0;font-size:24px;line-height:1.2;'
        f'font-weight:600;color:{INK};">{esc(d.verdict)}</h1>'
        f'<p style="margin:8px 0 14px 0;font-size:14px;line-height:1.55;'
        f'color:{MUTED};">{esc(d.verdict_blurb)}</p>{checks}</td></tr>')

    if d.indexes:
        cells = "".join(
            f'<td style="padding:12px 14px;font-family:{FONT};">'
            f'<div style="font-family:{MONO};font-size:12px;color:{MUTED};">'
            f'{esc(r["symbol"])}</div>'
            f'<div style="font-family:{MONO};font-size:17px;color:{INK};">'
            f'{esc(str(r.get("close", "—")))}</div>'
            f'<div style="font-size:11px;color:{DIM};">'
            + (f'{abs(r["vs_200_pct"]):.1f}% '
               f'{"above" if r.get("above_200") else "below"} its 200-day'
               if r.get("vs_200_pct") is not None else "200-day not available")
            + '</div></td>'
            for r in d.indexes)
        parts.append(
            f'<tr><td style="padding:6px 28px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="background-color:{RAISED};border-radius:10px;">'
            f'<tr>{cells}</tr></table></td></tr>')

    if d.watchlist_breakouts:
        body = _row(", ".join(
            f'<span style="font-family:{MONO};">{esc(r["symbol"])}</span>'
            for r in d.watchlist_breakouts))
        parts.append(_section("On your watchlist — broke out", body))

    if d.watchlist_events:
        body = "".join(
            _row(f'<span style="color:{WARN};">{esc(_day(e["date"]))}</span> '
                 f'<span style="font-family:{MONO};">{esc(e["ticker"])}</span>',
                 esc(e.get("type_label") or e.get("type", "")))
            for e in d.watchlist_events)
        parts.append(_section("On your watchlist — dated this week", body))

    if d.setups:
        body = "".join(
            _row(f'{esc(s["screen"])}',
                 esc(", ".join(r["symbol"] for r in s["rows"])))
            for s in d.setups)
        parts.append(_section("Set up", body))

    if d.week_events:
        body = "".join(
            _row(f'<span style="color:{WARN};">{esc(_day(e["date"]))}</span>',
                 esc(e["name"]))
            for e in d.week_events)
        parts.append(_section("Dated this week", body))

    if d.quiet:
        parts.append(_section("A quiet week", _row(
            "Nothing is set up and nothing is dated. That is a reading about "
            "the market, not a gap in this letter.")))

    parts.append(
        f'<tr><td style="padding:24px 28px 28px 28px;font-family:{FONT};'
        f'border-top:1px solid {BORDER};">'
        f'<p style="margin:14px 0 0 0;font-size:12px;line-height:1.5;color:{DIM};">'
        f'Measured at the {esc(d.as_of)} close. A screening and market-analytics '
        f'tool. Not investment advice. We are not a registered investment adviser.'
        f'</p>'
        f'<p style="margin:10px 0 0 0;font-size:12px;color:{DIM};">'
        f'<a href="{esc(site)}" style="color:{MUTED};">Open the site</a>'
        f' &nbsp;&middot;&nbsp; '
        f'<a href="{esc(unsubscribe_url)}" style="color:{MUTED};">Stop these emails</a>'
        f'</p></td></tr>')

    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="background-color:{BG};margin:0;padding:24px 12px;">'
        f'<tr><td align="center">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="max-width:520px;background-color:{CARD};'
        f'border:1px solid {BORDER};border-radius:14px;">'
        + "".join(parts) +
        f'</table></td></tr></table>'
    )
