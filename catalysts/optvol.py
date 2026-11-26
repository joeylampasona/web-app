"""How much traded in a company's options today, and where.

The nightly already downloads every contract on every expiry it reads for
gamma, and each row carries the session's volume. That column was being
thrown away. This keeps it: calls against puts, the day's trading against the
open interest already on the book, and the handful of contracts that did most
of it.

What it is, and is not. Volume says contracts changed hands. It does not say
who bought and who sold, whether a position was opened or closed, or whether
the other leg of a spread is sitting two strikes away. "Unusual" here means
one thing that can be checked: a contract traded several times what was open
in it. It is a place to look, not a reading of anybody's intent.

Two rules keep the figures honest:

  * A contract's volume counts only when it traded on the chain's latest
    session. Yahoo shows the volume of the last day a contract traded, and
    for a thin contract that day can be weeks back. Market Desk found the
    same thing reading the same chains.
  * Open interest is the clearing house's wherever it answered. Against
    Yahoo's own, which is missing for much of the book, a contract with none
    shown is not called unusual: the zero is Yahoo's, not the market's.

Nothing here reaches the network. The rows arrive with the chain.
"""
from __future__ import annotations

import datetime as dt
import json

#: A contract is unusual when it traded at least this many times what was
#: open in it...
UNUSUAL_MULTIPLE = 2.0
#: ...and at least this many contracts. Twelve against an open interest of
#: two is a multiple of six and a headline about nothing.
UNUSUAL_MIN_VOLUME = 500

#: How many of the busiest contracts are kept for a company.
TOP = 5

#: A company's day goes on the market board only at this many contracts.
#: Below it a ratio is mostly the smallness of the book.
BOARD_MIN_VOLUME = 2_000

#: How many companies the board carries.
BOARD_ROWS = 60

#: How old a stored day may be before the site stops showing it. Volume is
#: about one session; a week-old one beside today's price is another story.
MAX_AGE_DAYS = 5

#: Days of each company's volume kept, to say what is usual for it, and how
#: many earlier sessions that needs before it is said.
HISTORY_DAYS = 45
USUAL_MIN_SESSIONS = 5

COPY = {
    "header": "Where the day's option trading was large against what was already "
              "open: contracts traded, calls against puts, and the busiest "
              "strikes, for the names with a dated event ahead.",
    "subhead": "Ranked by the day's volume as a share of open interest, among "
               "names that traded at least 2,000 contracts.",
    "footer": "Volume says contracts changed hands, not who bought or why, and "
              "a busy strike may be one leg of a spread. A contract is marked "
              "unusual when it traded at least twice its open interest and at "
              "least 500 contracts. Open interest is published once a day and "
              "generally predates the session's trading. Not a signal.",
}


def _session(quoted: list[dict]) -> str | None:
    days = [row["traded"] for row in quoted if row.get("fresh") and row.get("traded")]
    return max(days).isoformat() if days else None


def summary(symbol: str, spot: float, quoted: list[dict], book=None) -> dict | None:
    """One company's option trading for the session, from its chain's rows.

    `quoted` is what yf.quoted_chain returns: expiry, side, strike, Yahoo's
    open interest, volume, and `fresh`. `book` is OCC's open interest keyed
    by (expiry, side, strike), or None to use Yahoo's own. None when the
    chain has neither volume nor open interest to speak of.
    """
    if not quoted:
        return None
    cleared = book is not None
    asked = {row["expiry"] for row in quoted}
    seen: set = set()
    calls = puts = held = traded = 0
    rows = []
    for row in quoted:
        key = (row["expiry"], row["side"], row["strike"])
        if key in seen:
            continue
        seen.add(key)
        interest = int(book.get(key, 0)) if cleared else int(row.get("oi") or 0)
        held += max(interest, 0)
        # Only a trade on the latest session is today's volume.
        volume = int(row.get("volume") or 0) if row.get("fresh") else 0
        if volume <= 0:
            continue
        traded += 1
        if row["side"] == "call":
            calls += volume
        else:
            puts += volume
        rows.append((volume, interest, row))
    if cleared:
        # Series the clearing house holds and Yahoo does not list are still
        # part of the book the day's trading is measured against.
        held += sum(int(n) for key, n in book.items()
                    if key[0] in asked and key not in seen and n > 0)
    total = calls + puts
    if total <= 0 and held <= 0:
        return None

    def unusual(volume: int, interest: int) -> bool:
        if volume < UNUSUAL_MIN_VOLUME:
            return False
        if interest <= 0:
            # Nothing open and five hundred traded is unusual by any count,
            # but only where the zero can be believed.
            return cleared
        return volume >= UNUSUAL_MULTIPLE * interest

    rows.sort(key=lambda item: (-item[0], item[2]["expiry"], item[2]["strike"],
                                item[2]["side"]))
    top = []
    for volume, interest, row in rows[:TOP]:
        top.append({
            "expiry": row["expiry"].isoformat(),
            "side": row["side"],
            "strike": round(float(row["strike"]), 2),
            "volume": volume,
            "open_interest": interest,
            "multiple": round(volume / interest, 1) if interest > 0 else None,
            "unusual": unusual(volume, interest),
            "vs_spot_pct": (round(100.0 * (row["strike"] / spot - 1.0), 1)
                            if spot and spot > 0 else None),
        })
    return {
        "symbol": symbol.upper(),
        "session": _session(quoted),
        "spot": round(float(spot), 4) if spot else None,
        "volume": total,
        "call_volume": calls,
        "put_volume": puts,
        # Puts for every call. None with no calls traded, which is not zero.
        "put_call": round(puts / calls, 2) if calls > 0 else None,
        "open_interest": held,
        # The day's trading as a share of what was open. None with no book.
        "volume_oi": round(total / held, 3) if held > 0 else None,
        "contracts_traded": traded,
        "unusual": sum(1 for volume, interest, _ in rows if unusual(volume, interest)),
        "expiries": len(asked),
        "oi_source": "occ" if cleared else "yahoo",
        "top": top,
    }


# ---------------------------------------------------------------- storage
#
# The catalysts stage computes and writes; publish reads and never reaches
# the network. A row a session, so that after a week there is something to
# call usual for each company.

def store(conn, found: dict[str, dict], as_of: dt.date) -> int:
    """Keep tonight's summaries. Returns rows written."""
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    written = 0
    for symbol, payload in found.items():
        if not payload:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO options_volume"
            "(symbol, as_of, volume, payload, fetched_at) VALUES (?,?,?,?,?)",
            (symbol.upper(), as_of.isoformat(), int(payload.get("volume") or 0),
             json.dumps(payload, separators=(",", ":")), now))
        written += 1
    cutoff = (as_of - dt.timedelta(days=HISTORY_DAYS)).isoformat()
    conn.execute("DELETE FROM options_volume WHERE as_of < ?", (cutoff,))
    conn.commit()
    return written


def load(conn, symbols, as_of: dt.date, max_age_days: int = MAX_AGE_DAYS
         ) -> dict[str, dict]:
    """The newest stored day for each of these names, with what is usual.

    `usual_volume` is the mean of the company's earlier stored sessions and
    `vs_usual` the newest day against it; both None until there are
    USUAL_MIN_SESSIONS earlier ones. `stale` when the day stored is not this
    edition's.
    """
    wanted = {s.upper() for s in symbols}
    cutoff = (as_of - dt.timedelta(days=max_age_days)).isoformat()
    history: dict[str, list[tuple[str, int]]] = {}
    newest: dict[str, tuple[str, str]] = {}
    try:
        rows = conn.execute(
            "SELECT symbol, as_of, volume, payload FROM options_volume"
            " WHERE as_of <= ? ORDER BY symbol, as_of", (as_of.isoformat(),)).fetchall()
    except Exception:                               # noqa: BLE001 - table not there yet
        return {}
    for row in rows:
        symbol = row[0]
        if symbol not in wanted:
            continue
        history.setdefault(symbol, []).append((row[1], int(row[2] or 0)))
        newest[symbol] = (row[1], row[3])
    out: dict[str, dict] = {}
    for symbol, (day, raw) in newest.items():
        if day < cutoff:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        earlier = [volume for stored, volume in history[symbol] if stored < day]
        usual = (sum(earlier) / len(earlier)
                 if len(earlier) >= USUAL_MIN_SESSIONS else None)
        payload["as_of"] = day
        payload["stale"] = day < as_of.isoformat()
        payload["usual_volume"] = round(usual) if usual else None
        payload["usual_sessions"] = len(earlier)
        payload["vs_usual"] = (round(payload.get("volume", 0) / usual, 1)
                               if usual else None)
        out[symbol] = payload
    return out


def board(found: dict[str, dict] | None) -> list[dict]:
    """The market ranking: the day's volume against open interest, among the
    names that traded enough for the ratio to mean something. Ties break on
    the symbol so two runs over the same data rank the same."""
    rows = [payload for payload in (found or {}).values()
            if payload and (payload.get("volume") or 0) >= BOARD_MIN_VOLUME
            and payload.get("volume_oi") is not None]
    rows.sort(key=lambda row: (-(row["volume_oi"] or 0.0), row["symbol"]))
    return rows
