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

# The site's light theme: the printed market page. Paper, ink, one lime
# highlighter, square corners, an ink rule over each department.
BG      = "#F2F4F3"   # --surface-0, the paper
CARD    = "#F8F9F8"   # --surface-1
RAISED  = "#FFFFFF"   # --surface-2
INK     = "#101412"   # --text-primary, and --rule
MUTED   = "#3A433F"   # --text-secondary
DIM     = "#5A645F"   # --text-muted
BORDER  = "#C5CCC8"   # --border
BRAND   = "#D8F23A"   # --brand, the highlighter
ONBRAND = "#101412"   # --on-brand
GAIN    = "#0B6B3A"   # --gain
LOSS    = "#B3261E"   # --loss
WARN    = "#A16207"   # --warn
TAPE_MUTED = "#AEB8B2"  # --tape-muted

# The site's faces first, for the clients that have them; each stack falls
# back to something of the same build, so the letter keeps its shape without.
FONT = ("'IBM Plex Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif")
DISPLAY = ("'IBM Plex Sans Condensed','Arial Narrow','Helvetica Neue',Helvetica,Arial,sans-serif")
MONO = "'IBM Plex Mono','SF Mono',Menlo,Consolas,monospace"
PAD = "28px"


def _day(iso: str) -> str:
    try:
        return dt.date.fromisoformat(iso).strftime("%a %-d %b")
    except (ValueError, TypeError):
        return iso or ""


def text(d: Digest, site: str, unsubscribe_url: str) -> str:
    """The plain-text part. Written to be read, not as a fallback nobody sees."""
    lines = ["THE TAPE — the week ahead", f"Measured at the {d.as_of} close.", ""]
    lines += [d.verdict.upper(), d.verdict_blurb, ""]
    for c in d.checks:
        lines.append(f"  - {c}")

    if d.indexes:
        lines.append("")
        for row in d.indexes:
            side = ("above" if row.get("above_200") else "below") \
                if row.get("above_200") is not None else "—"
            lines.append(f"  {row['symbol']}  {row['close']}  ({side} its 200-day)")

    if d.radar:
        lines += ["", "WHERE STRENGTH SITS", f"  {d.radar['label']}: {d.radar['sub']}"]
        for row in _radar_pairs(d.radar):
            lines.append(f"  {row}")
        for row in _radar_groups(d.radar):
            lines.append(f"  {row}")

    if d.tenths:
        lines += ["", "THE MARKET IN TEN CELLS",
                  "  Share of each tenth of the ranking above both its 50- and 200-day",
                  "  lines, strongest tenth first:",
                  "  " + "  ".join(f"{v}%" for v in d.tenths)]

    if d.setups:
        lines += ["", "SET UP"]
        for s in d.setups:
            names = ", ".join(r["symbol"] for r in s["rows"])
            lines.append(f"  {s['screen']} ({s['total']}): {names}")

    if d.week_events:
        lines += ["", "DATED THIS WEEK"]
        for e in d.week_events:
            lines.append(f"  {_day(e['date'])}  {e['name']}")

    if d.priced_moves:
        lines += ["", "PRICED FOR THE BIGGEST MOVES ON EARNINGS"]
        for r in d.priced_moves:
            lines.append(f"  {_day(r['date'])}  {r['symbol']}  ±{r['priced']:.1f}%")
        lines.append(f"  {_priced_note(d.priced_record)}")

    if d.quiet:
        lines += ["", "Nothing is set up and nothing is dated. A quiet week is a",
                  "quiet week — there is no reading hidden in it."]

    lines += ["", "—",
              "A screening and market-analytics tool. Not investment advice.",
              "We are not a registered investment adviser.",
              f"Open the site: {site}",
              f"Stop these emails: {unsubscribe_url}"]
    return "\n".join(lines)


def _pct(v) -> str:
    return "—" if v is None else f"{v:+.1f}%"


def _radar_pairs(r: dict) -> list[str]:
    """Each key ratio over six months, and where it stood a week before."""
    return [f"{p['label']}: {_pct(p['rs126'])} over six months"
            + (f" (from {_pct(p['start126'])})" if p.get("start126") is not None else "")
            for p in r["pairs"]]


def _radar_groups(r: dict) -> list[str]:
    out = []
    if r.get("leaders"):
        out.append("Leading groups: " + ", ".join(r["leaders"]))
    if r.get("weakest"):
        out.append("Weakest: " + ", ".join(r["weakest"]))
    if r.get("front") is not None:
        line = f"{r['front']} stocks on the front line, ahead of an industry that leads the market"
        if r.get("front_week_ago") is not None:
            line += f" ({r['front_week_ago']} a week ago)"
        out.append(line)
    return out


def _priced_note(record: dict | None) -> str:
    """What the priced move is, and how often it has held."""
    base = ("The at-the-money straddle at the first expiry after the report: "
            "how big a move the options pay for, either way.")
    if not record:
        return base
    return (f"{base} The actual move has stayed inside it on "
            f"{record['inside_pct']}% of the last {record['n']} reports read.")


def _long_day(iso: str) -> str:
    try:
        return dt.date.fromisoformat(iso).strftime("%b %-d, %Y")
    except (ValueError, TypeError):
        return iso or ""


def _caps(text_: str, colour: str = DIM, size: int = 11) -> str:
    return (f'<span style="font-family:{MONO};font-size:{size}px;letter-spacing:0.12em;'
            f'text-transform:uppercase;color:{colour};">{text_}</span>')


def _section(title: str, body: str, aside: str = "") -> str:
    """A department: its name in the display face on an ink rule."""
    return (
        f'<tr><td style="padding:26px {PAD} 0 {PAD};font-family:{FONT};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="font-family:{DISPLAY};font-size:22px;font-weight:700;color:{INK};'
        f'padding:0 0 6px 0;border-bottom:1px solid {INK};">{esc(title)}</td>'
        f'<td align="right" style="padding:0 0 6px 0;border-bottom:1px solid {INK};">'
        f'{_caps(esc(aside)) if aside else ""}</td></tr></table>'
        f'{body}</td></tr>'
    )


def _row(left: str, right: str = "") -> str:
    """One ruled line: what it is on the left, the figures on the right."""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="padding:9px 12px 9px 0;border-bottom:1px solid {BORDER};font-size:14px;'
        f'line-height:1.45;color:{INK};vertical-align:top;">{left}</td>'
        + (f'<td align="right" style="padding:9px 0;border-bottom:1px solid {BORDER};'
           f'font-size:13px;line-height:1.5;color:{MUTED};vertical-align:top;">{right}</td>'
           if right else "")
        + '</tr></table>'
    )


def _note(text_: str) -> str:
    return (f'<p style="margin:10px 0 0 0;font-size:12px;line-height:1.5;color:{DIM};">'
            f'{text_}</p>')


def _headline(verdict: str) -> str:
    """The verdict with the phrase that carries it under the highlighter, the
    way the home page marks it."""
    mark = (f'background-color:{BRAND};color:{ONBRAND};padding:0 8px;')
    lead = "The tape is "
    if verdict.startswith(lead):
        return f'{esc(lead)}<span style="{mark}">{esc(verdict[len(lead):])}.</span>'
    if "," in verdict:
        head, rest = verdict.split(",", 1)
        return f'<span style="{mark}">{esc(head)}</span>,{esc(rest)}.'
    return f'<span style="{mark}">{esc(verdict)}.</span>'


STATE = {1: "In gear", 0: "Neither", -1: "Against"}


def _meter(cells: list[dict]) -> str:
    """The four checks, a cell each: lit in lime when in gear, edged in red
    when against, and each says which in words."""
    out = []
    for i, c in enumerate(cells):
        lit, against = c["score"] == 1, c["score"] == -1
        out.append(
            f'<td width="{100 // len(cells)}%" style="vertical-align:top;padding:10px 10px 12px 10px;'
            f'background-color:{BRAND if lit else RAISED};'
            f'border-top:6px solid {INK if lit else LOSS if against else BORDER};'
            f'border-bottom:1px solid {INK};'
            + (f'border-left:1px solid {BORDER};' if i else "")
            + f'font-family:{FONT};">'
            f'<div style="font-family:{MONO};font-size:9px;letter-spacing:0.08em;'
            f'text-transform:uppercase;color:{MUTED};line-height:1.35;">{esc(c["label"])}</div>'
            f'<div style="font-family:{MONO};font-size:22px;font-weight:700;color:{INK};'
            f'padding:6px 0 2px 0;white-space:nowrap;">{esc(c["value"])}</div>'
            f'<div style="font-size:12px;color:{MUTED};">{STATE[c["score"]]}</div></td>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin:18px 0 0 0;border-left:1px solid {INK};border-right:1px solid {INK};">'
            f'<tr>{"".join(out)}</tr></table>')


RATIO_SCALE = 8.0   # a ratio's bar runs out to this many percent either side


def _ratio(p: dict) -> str:
    """One key ratio as a bar from a centre line: right ahead, left behind."""
    v = p.get("rs126")
    if v is None:
        return ""
    width = round(min(100.0, abs(v) / RATIO_SCALE * 100))
    tone = GAIN if v >= 0 else LOSS
    bar = (f'<table role="presentation" width="{max(width, 2)}%" cellpadding="0" cellspacing="0" '
           f'border="0" align="{"left" if v >= 0 else "right"}"><tr>'
           f'<td height="10" style="background-color:{tone};font-size:0;line-height:0;">&nbsp;</td>'
           f'</tr></table>')
    half = f'width="50%" height="10" style="background-color:#E4E8E5;font-size:0;line-height:0;'
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:12px 0 0 0;"><tr>'
        f'<td style="font-size:13px;color:{INK};padding:0 0 4px 0;">{esc(p["label"])}</td>'
        f'<td align="right" style="font-family:{MONO};font-size:13px;font-weight:700;color:{tone};'
        f'padding:0 0 4px 0;">{esc(_pct(v))}</td></tr></table>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td {half}border-right:2px solid {INK};">{bar if v < 0 else "&nbsp;"}</td>'
        f'<td {half}">{bar if v >= 0 else "&nbsp;"}</td></tr></table>')


def _tenths(values: list[int]) -> str:
    """The breadth barcode at ten cells: the share of each tenth of the
    ranking above both its lines, strongest tenth on the left."""
    def cell(v: int) -> str:
        if v >= 50:
            alpha = 0.25 + 0.75 * (v - 50) / 50
            bg, ink = f"rgba(11,107,58,{alpha:.2f})", ("#FFFFFF" if v >= 75 else INK)
        else:
            alpha = 0.25 + 0.75 * (50 - v) / 50
            bg, ink = f"rgba(179,38,30,{alpha:.2f})", ("#FFFFFF" if v <= 25 else INK)
        # A solid colour first, for the clients that drop rgba.
        solid = GAIN if v >= 75 else "#9CC9B0" if v >= 50 else "#E3B1AC" if v > 25 else LOSS
        return (f'<td width="10%" align="center" height="34" bgcolor="{solid}" '
                f'style="background-color:{bg};font-family:{MONO};font-size:11px;'
                f'font-weight:700;color:{ink};">{v}%</td>')
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:12px 0 0 0;border:1px solid {INK};"><tr>'
        + "".join(cell(v) for v in values) + '</tr></table>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="padding:4px 0 0 0;">{_caps("Strongest tenth", DIM, 9)}</td>'
        f'<td align="right" style="padding:4px 0 0 0;">{_caps("Weakest tenth", DIM, 9)}</td>'
        f'</tr></table>')


def html(d: Digest, site: str, unsubscribe_url: str) -> str:
    parts: list[str] = []

    # ---- masthead, on an ink rule
    parts.append(
        f'<tr><td style="padding:22px {PAD} 12px {PAD};border-bottom:3px solid {INK};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="font-family:{DISPLAY};font-size:24px;font-weight:700;letter-spacing:0.04em;'
        f'color:{INK};white-space:nowrap;">'
        f'<span style="display:inline-block;width:13px;height:13px;background-color:{BRAND};'
        f'border:2px solid {INK};vertical-align:-1px;">&nbsp;</span>&nbsp; THE TAPE</td>'
        f'<td align="right">{_caps("The week ahead &middot; " + esc(_long_day(d.as_of)))}</td>'
        f'</tr></table></td></tr>')

    # ---- the tape strip: the indexes, white on ink
    if d.indexes:
        cells = "".join(
            f'<td style="padding:9px 14px 9px 0;font-family:{MONO};font-size:12px;'
            f'color:{TAPE_MUTED};white-space:nowrap;">{esc(r["symbol"])} '
            f'<span style="color:#FFFFFF;font-weight:700;">{esc(str(r.get("close", "—")))}</span>'
            + (f' <span style="color:{"#7BD8A4" if r.get("above_200") else "#F2A08F"};">'
               f'{"▲" if r.get("above_200") else "▼"} {abs(r["vs_200_pct"]):.1f}% '
               f'{"over" if r.get("above_200") else "under"} 200d</span>'
               if r.get("vs_200_pct") is not None else "")
            + '</td>'
            for r in d.indexes[:3])
        parts.append(
            f'<tr><td style="background-color:{INK};padding:0 {PAD};">'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'{cells}</tr></table></td></tr>')

    # ---- the read
    in_gear = sum(1 for c in d.meter if c["score"] == 1)
    kicker = "The read" + (f" &middot; {in_gear} of {len(d.meter)} checks in gear" if d.meter else "")
    lead = (
        f'<tr><td style="padding:26px {PAD} 0 {PAD};font-family:{FONT};">'
        f'{_caps(kicker)}'
        f'<h1 style="margin:10px 0 0 0;font-family:{DISPLAY};font-size:44px;line-height:1.08;'
        f'font-weight:700;color:{INK};">{_headline(d.verdict)}</h1>'
        f'<p style="margin:14px 0 0 0;font-size:16px;line-height:1.5;color:{MUTED};">'
        f'{esc(d.verdict_blurb)}</p>')
    if d.meter:
        lead += _meter(d.meter)
    lead += "".join(
        f'<p style="margin:{10 if i == 0 else 3}px 0 0 0;font-size:13px;line-height:1.5;'
        f'color:{MUTED};">&middot; {esc(c)}</p>' for i, c in enumerate(d.checks))
    parts.append(lead + '</td></tr>')

    if d.radar:
        body = (f'<p style="margin:12px 0 0 0;font-family:{DISPLAY};font-size:26px;font-weight:700;'
                f'line-height:1.15;color:{INK};">{esc(d.radar["label"])}</p>'
                f'<p style="margin:4px 0 0 0;font-size:14px;line-height:1.5;color:{MUTED};">'
                f'{esc(d.radar["sub"])}</p>')
        body += "".join(_ratio(p) for p in d.radar["pairs"])
        body += f'<div style="height:10px;line-height:10px;font-size:0;">&nbsp;</div>'
        body += "".join(_row(esc(line)) for line in _radar_groups(d.radar))
        body += _note(f'Bars run from the centre line: right is ahead of the S&amp;P 500 over '
                      f'six months, left is behind, out to &plusmn;{RATIO_SCALE:.0f}%. '
                      f'Measured, not forecast.')
        parts.append(_section("Where strength sits", body, "six months"))

    if d.tenths:
        parts.append(_section(
            "The market in ten cells",
            _tenths(d.tenths)
            + _note("Every ranked stock, strongest tenth on the left. Each cell is the share "
                    "of that tenth above both its 50-day and 200-day lines."),
            "breadth"))

    if d.setups:
        body = "".join(
            _row(f'<strong>{esc(s["screen"])}</strong> '
                 f'<span style="font-family:{MONO};font-size:12px;color:{DIM};">{s["total"]}</span>',
                 f'<span style="font-family:{MONO};color:{INK};">'
                 + esc("  ".join(r["symbol"] for r in s["rows"])) + '</span>')
            for s in d.setups)
        parts.append(_section("Set up", body, "by screen"))

    if d.week_events:
        body = "".join(
            _row(f'<span style="font-family:{MONO};font-size:12px;color:{DIM};">'
                 f'{esc(_day(e["date"]).upper())}</span> &nbsp;{esc(e["name"])}')
            for e in d.week_events)
        parts.append(_section("Dated this week", body))

    if d.priced_moves:
        body = "".join(
            _row(f'<span style="font-family:{MONO};font-size:12px;color:{DIM};">'
                 f'{esc(_day(r["date"]).upper())}</span> &nbsp;'
                 f'<span style="font-family:{MONO};font-weight:700;">{esc(r["symbol"])}</span>',
                 f'<span style="font-family:{MONO};font-weight:700;color:{ONBRAND};'
                 f'background-color:{BRAND};padding:1px 6px;">&plusmn;{r["priced"]:.1f}%</span>')
            for r in d.priced_moves)
        body += _note(esc(_priced_note(d.priced_record)))
        parts.append(_section("Priced for the biggest moves", body, "earnings"))

    if d.quiet:
        parts.append(_section("A quiet week", _row(
            "Nothing is set up and nothing is dated. That is a reading about "
            "the market, not a gap in this letter.")))

    parts.append(
        f'<tr><td style="padding:28px {PAD} 0 {PAD};">'
        f'<a href="{esc(site)}" style="display:inline-block;background-color:{BRAND};'
        f'color:{ONBRAND};font-family:{FONT};font-size:14px;font-weight:700;'
        f'text-decoration:none;padding:11px 18px;border:1px solid {INK};">'
        f'Open tonight&rsquo;s page</a></td></tr>'
        f'<tr><td style="padding:22px {PAD} 28px {PAD};font-family:{FONT};">'
        f'<p style="margin:0;padding:14px 0 0 0;border-top:1px solid {BORDER};font-size:12px;'
        f'line-height:1.5;color:{DIM};">'
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
        f'border="0" style="max-width:600px;background-color:{CARD};'
        f'border:1px solid {BORDER};">'
        + "".join(parts) +
        f'</table></td></tr></table>'
    )
