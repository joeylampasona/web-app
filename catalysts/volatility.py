"""The VIX against its three-month version, in one line.

The VIX is what S&P 500 options price for the next thirty days; VIX3M is the
same thing for the next three months. Ordinarily the further one is higher:
more can happen in three months than in one. When the near one climbs above
it, the market is paying more for protection now than for protection later,
which is what fear with a date on it looks like.

Two numbers and their ratio, stated with their date, and one plain word for
the state. It is a description of what options cost, not a forecast: the
ratio has been above one at bottoms and at the start of long declines both.

Both come from Yahoo's quote endpoint, the one the delayed prices use, as
^VIX and ^VIX3M. Read once a night in the stage that reaches the network,
never raising; a night it does not answer keeps the last reading with its
own date on it.
"""
from __future__ import annotations

import datetime as dt
import json
import logging

from data import settings, store

log = logging.getLogger(__name__)

KV_KEY = "volatility.history"
SYMBOLS = ("^VIX", "^VIX3M")

#: Sessions of readings kept.
KEPT = 60

#: A reading older than this many days is not shown as the state of things.
MAX_AGE_DAYS = 5

# The bands, in the order they are tried. The first that fits is the word.
#
#   stressed   the near month is priced at or above the three-month, or the
#              VIX is at thirty or more
#   uneasy     the gap between them has nearly closed (ratio 0.95 or more),
#              or the VIX is at twenty or more
#   calm       the VIX is under fifteen and well under the three-month
#              (ratio below 0.90)
#   ordinary   everything else
STRESSED_RATIO, STRESSED_VIX = 1.00, 30.0
UNEASY_RATIO, UNEASY_VIX = 0.95, 20.0
CALM_RATIO, CALM_VIX = 0.90, 15.0


def state(vix: float, vix3m: float | None) -> str:
    """One word for where the two sit. Without the three-month figure the
    level alone decides."""
    ratio = vix / vix3m if vix3m and vix3m > 0 else None
    if vix >= STRESSED_VIX or (ratio is not None and ratio >= STRESSED_RATIO):
        return "stressed"
    if vix >= UNEASY_VIX or (ratio is not None and ratio >= UNEASY_RATIO):
        return "uneasy"
    if vix < CALM_VIX and (ratio is None or ratio < CALM_RATIO):
        return "calm"
    return "ordinary"


def reading(vix, vix3m, as_of: str | None) -> dict | None:
    """The published shape for one session, or None without a VIX."""
    try:
        vix = float(vix)
    except (TypeError, ValueError):
        return None
    if not vix > 0:
        return None
    try:
        far = float(vix3m)
        far = far if far > 0 else None
    except (TypeError, ValueError):
        far = None
    return {
        "as_of": as_of,
        "vix": round(vix, 2),
        "vix3m": round(far, 2) if far else None,
        "ratio": round(vix / far, 3) if far else None,
        "state": state(vix, far),
    }


def _history(conn) -> list[dict]:
    try:
        kept = json.loads(store.get_kv(conn, KV_KEY, "") or "[]")
        return [row for row in kept if isinstance(row, dict) and row.get("as_of")]
    except ValueError:
        return []


def _fetch() -> dict | None:
    """Tonight's two quotes as a reading, or None when Yahoo has no VIX."""
    from catalysts import yf                       # noqa: PLC0415 - optional
    found = yf.quotes(list(SYMBOLS))
    near, far = found.get("^VIX") or {}, found.get("^VIX3M") or {}
    # The day the VIX last printed, in New York, which is the session the
    # reading is of. At two in the morning that is yesterday's close.
    day = str(near.get("at") or "")[:10] or None
    return reading(near.get("last"), far.get("last"), day)


def refresh(conn, session: dt.date, notice=None, fetch=None) -> dict | None:
    """Read tonight's levels and keep them. Never raises; returns the
    reading kept, or None when there was none to keep."""
    try:
        if settings.get("data.provider") == "synthetic":
            found = _synthetic(session)
        else:
            found = (fetch or _fetch)()
    except Exception as exc:                        # noqa: BLE001 - never the nightly
        if notice:
            notice(f"volatility: not read tonight ({type(exc).__name__}).")
        return None
    if not found:
        if notice:
            notice("volatility: Yahoo gave no VIX tonight; the last reading stands.")
        return None
    found["as_of"] = found.get("as_of") or session.isoformat()
    history = [row for row in _history(conn) if row["as_of"] != found["as_of"]]
    history.append(found)
    history = sorted(history, key=lambda row: row["as_of"])[-KEPT:]
    store.set_kv(conn, KV_KEY, json.dumps(history, separators=(",", ":")))
    if notice:
        far = f", three-month {found['vix3m']:.2f}" if found.get("vix3m") else ""
        ratio = f", ratio {found['ratio']:.2f}" if found.get("ratio") else ""
        notice(f"volatility: VIX {found['vix']:.2f}{far}{ratio}: {found['state']} "
               f"({found['as_of']}).")
    return found


def latest(conn, as_of: dt.date) -> dict | None:
    """The newest reading on file, with the one before it for the change.
    None when there is none recent enough to call the state of things."""
    history = [row for row in _history(conn) if row["as_of"] <= as_of.isoformat()]
    if not history:
        return None
    newest = history[-1]
    try:
        age = (as_of - dt.date.fromisoformat(newest["as_of"])).days
    except ValueError:
        return None
    if age > MAX_AGE_DAYS:
        return None
    out = dict(newest)
    out["previous_vix"] = history[-2]["vix"] if len(history) > 1 else None
    out["source"] = "Yahoo"
    return out


def _synthetic(session: dt.date) -> dict:
    """A fixture reading, fixed by the date so two runs agree."""
    import random                                  # noqa: PLC0415
    rng = random.Random(session.toordinal())
    vix = round(rng.uniform(13.0, 27.0), 2)
    return reading(vix, round(vix * rng.uniform(0.92, 1.18), 2), session.isoformat())
