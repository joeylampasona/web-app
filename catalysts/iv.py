"""Implied volatility around a dated catalyst.

Three rules, enforced here and stated in the UI:
  1. Only ticker-owned dated events qualify. Macro days light up the whole tape
     and say nothing about one name, so they are never ingested at all.
  2. High IV is never itself a catalyst. It is a pricing observation about a
     date that already exists.
  3. No dated catalyst, no row. A rich expiry with nothing scheduled inside it
     is not information, it is a shrug.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from data import settings
from data.adapters import DataAdapter, get_adapter
from data.types import OptionChain
from catalysts.events import Calendar, Event


@dataclass
class IVRow:
    ticker: str
    name: str
    event_type: str
    event_label: str
    event_date: dt.date
    confirmed: str
    days_until: int
    catalyst_expiry: dt.date
    catalyst_iv: float
    neighbour_iv: float
    iv_richness: float
    iv_band: str
    dots: int
    week_of: str
    neighbours: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "ticker": self.ticker, "name": self.name,
            "event_type": self.event_type, "event_label": self.event_label,
            "event_date": self.event_date.isoformat(), "confirmed": self.confirmed,
            "days_until": self.days_until,
            "catalyst_expiry": self.catalyst_expiry.isoformat(),
            "catalyst_iv": round(self.catalyst_iv, 4),
            "neighbour_iv": round(self.neighbour_iv, 4),
            "iv_richness": round(self.iv_richness, 3),
            "iv_band": self.iv_band, "dots": self.dots,
            "week_of": self.week_of, "neighbours": self.neighbours,
        }

    @classmethod
    def from_json(cls, payload: dict, as_of: dt.date | None = None) -> "IVRow":
        """Rebuild a row from its published form.

        `as_of`, when given, re-dates the countdown against that session rather
        than trusting the one stored with the row. A row read back on a later
        session would otherwise say "in 27 days" about a date that is now 26
        away, which is the kind of small lie that survives for weeks because
        nothing ever contradicts it.
        """
        event_date = dt.date.fromisoformat(payload["event_date"])
        days = (payload["days_until"] if as_of is None
                else (event_date - as_of).days)
        return cls(
            ticker=payload["ticker"], name=payload["name"],
            event_type=payload["event_type"], event_label=payload["event_label"],
            event_date=event_date, confirmed=payload["confirmed"],
            days_until=days,
            catalyst_expiry=dt.date.fromisoformat(payload["catalyst_expiry"]),
            catalyst_iv=float(payload["catalyst_iv"]),
            neighbour_iv=float(payload["neighbour_iv"]),
            iv_richness=float(payload["iv_richness"]),
            iv_band=payload["iv_band"], dots=int(payload["dots"]),
            week_of=payload["week_of"], neighbours=payload.get("neighbours") or [],
        )


BAND_LABELS = {"very_high": "Very high", "high": "High",
               "moderate": "Moderate", "low": "Low"}


def band_for(richness: float) -> tuple[str, int]:
    bands = settings.get("iv.bands", {}) or {}
    dots = int(settings.get("iv.dots", 5))
    if richness >= float(bands.get("very_high", 1.35)):
        return "very_high", dots
    if richness >= float(bands.get("high", 1.20)):
        return "high", max(1, dots - 1)
    if richness >= float(bands.get("moderate", 1.08)):
        return "moderate", max(1, dots - 2)
    return "low", max(1, dots - 3)


def _bracketing(chain: OptionChain, target: dt.date):
    """The expiry that brackets the event, plus its two neighbours."""
    expiries = sorted(chain.expiries, key=lambda e: e.expiry)
    for i, row in enumerate(expiries):
        if row.expiry >= target:
            before = expiries[i - 1] if i > 0 else None
            after = expiries[i + 1] if i + 1 < len(expiries) else None
            return row, [e for e in (before, after) if e is not None]
    return None, []


def compute(calendar: Calendar, symbols, names: dict[str, str],
            adapter: DataAdapter | None = None,
            gamma_out: dict | None = None,
            stats: dict | None = None) -> list[IVRow]:
    """Implied-volatility richness per name, and optionally gamma alongside it.

    `gamma_out`, when given, is filled with one GammaProfile per symbol whose
    chain carried usable open interest. It is an out-parameter rather than a
    second return value because the chain download is the expensive part of
    this stage and both readings come from it: asking for gamma separately
    would fetch every chain twice.

    `stats`, when given, is filled with counts of what happened on the way.
    Without it, "no name returned usable open interest" is a true statement
    covering two completely different faults — nobody answered the phone, or
    everybody answered and none of them had the field — and the fix differs.
    The counts cost nothing and are the difference between a diagnosis and a
    guess the next time this section renders empty.
    """
    from catalysts import gamma as gammamod          # noqa: PLC0415 - avoids a cycle
    from data import settings as settingsmod         # noqa: PLC0415

    adapter = adapter or get_adapter()
    rate = float(settingsmod.get("catalysts.risk_free_rate", 0.0) or 0.0)
    counts = stats if stats is not None else {}
    for key in ("asked", "no_event", "chain_none", "chain_error",
                "chain_empty", "chain_ok", "no_spot", "gamma_ok"):
        counts.setdefault(key, 0)

    rows: list[IVRow] = []
    for symbol in sorted(set(symbols)):
        counts["asked"] += 1
        event: Event | None = calendar.next_owned(symbol)
        if event is None:
            counts["no_event"] += 1
            continue                              # rule 3
        try:
            chain = adapter.get_option_chain(symbol)
        except NotImplementedError:
            chain = None
        except Exception:                         # noqa: BLE001
            # Still swallowed -- one bad name must not end the sweep -- but no
            # longer invisible. This branch firing for every name is what a
            # throttled night looks like, and it used to be indistinguishable
            # from a market with no listed options.
            counts["chain_error"] += 1
            chain = None
        if chain is None:
            counts["chain_none"] += 1
            continue
        if not chain.rows:
            counts["chain_empty"] += 1
        else:
            counts["chain_ok"] += 1
        # Before the IV-specific tests below. A chain whose expiries do not
        # bracket the event still has open interest at strikes, and that is a
        # separate reading from whether the event is priced richly.
        if gamma_out is not None:
            # Counted separately because it is the failure that already
            # happened once: gamma needs the underlying's price and implied
            # volatility does not, so a broken spot empties one section and
            # leaves the other looking healthy on the very same fetch.
            if chain.spot <= 0:
                counts["no_spot"] += 1
            found = gammamod.profile(chain, calendar.as_of, rate)
            if found is not None:
                gamma_out[symbol] = found
                counts["gamma_ok"] += 1
        if not chain.expiries:
            continue
        bracket, neighbours = _bracketing(chain, event.date)
        if bracket is None or not neighbours:
            continue
        neighbour_iv = sum(n.implied_volatility for n in neighbours) / len(neighbours)
        if neighbour_iv <= 0:
            continue
        richness = bracket.implied_volatility / neighbour_iv
        band, dots = band_for(richness)
        monday = event.date - dt.timedelta(days=event.date.weekday())
        rows.append(IVRow(
            ticker=symbol, name=names.get(symbol, symbol),
            event_type=event.type, event_label=event.title or event.type,
            event_date=event.date, confirmed=event.confirmed,
            days_until=event.days_until(calendar.as_of),
            catalyst_expiry=bracket.expiry,
            catalyst_iv=bracket.implied_volatility,
            neighbour_iv=neighbour_iv, iv_richness=richness,
            iv_band=band, dots=dots, week_of=monday.isoformat(),
            neighbours=[{"expiry": n.expiry.isoformat(),
                         "iv": round(n.implied_volatility, 4)} for n in neighbours],
        ))
    rows.sort(key=lambda r: (-r.catalyst_iv, r.days_until))
    return rows


COPY = {
    "header": "The highest-IV names already tied to a dated catalyst in the next few "
              "weeks. The score is how much richer that date is than the ones around "
              "it. High IV is never itself a catalyst.",
    "subhead": "Ticker-owned events only, ranked by implied volatility.",
    "footer": "Macro days — CPI, FOMC, payrolls — are skipped. They light up the whole "
              "tape and tell you nothing about one name.",
}


# How long a stored set stays usable. Implied volatility moves daily, so an
# old set is a worse answer than a fresh one — but it is a far better answer
# than the empty page a throttled night produces, and the rows carry their own
# session so the site can say which night they describe.
MAX_AGE_DAYS = 4

#: One blob in the existing kv table rather than a table of its own. These rows
#: are written whole, read whole, and never queried by column, so a table would
#: be a schema change earning nothing.
KV_KEY = "iv.rows"


def store(conn, rows: list[IVRow], as_of: dt.date) -> int:
    """Keep what was computed, so publish never has to fetch it again.

    The catalysts stage reaches the network and publish does not — the same
    split gamma, forecasts and the earnings cache already use. Implied
    volatility was the one reading that ignored it: `compute` ran in both
    stages, so a night Yahoo throttled the second run published zero rows over
    the several hundred the first run had just found, and every step went
    green. That is what this exists to stop.
    """
    import json                                   # noqa: PLC0415

    payload = {
        "as_of": as_of.isoformat(),
        "stored_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "rows": [r.to_json() for r in rows],
    }
    from data import store as storemod            # noqa: PLC0415
    storemod.set_kv(conn, KV_KEY, json.dumps(payload, separators=(",", ":")))
    return len(rows)


def load(conn, as_of: dt.date, max_age_days: int = MAX_AGE_DAYS
         ) -> tuple[list[IVRow], dt.date | None]:
    """Stored rows, and the session they describe.

    Returns an empty list and None when there is nothing usable, which the
    caller must be able to tell apart from "the market has no rich options" —
    the reason the session comes back alongside the rows rather than being
    buried in them.

    Rows whose event has already passed are dropped: a countdown that has run
    out is not a catalyst, and re-dating it would print a negative.
    """
    import json                                   # noqa: PLC0415
    from data import store as storemod            # noqa: PLC0415

    raw = storemod.get_kv(conn, KV_KEY, "")
    if not raw:
        return [], None
    try:
        payload = json.loads(raw)
        stored_as_of = dt.date.fromisoformat(payload["as_of"])
    except (TypeError, ValueError, KeyError):
        return [], None
    if (as_of - stored_as_of).days > max_age_days:
        return [], None

    out: list[IVRow] = []
    for item in payload.get("rows") or []:
        try:
            row = IVRow.from_json(item, as_of=as_of)
        except (TypeError, ValueError, KeyError):
            continue
        if row.days_until < 0:
            continue
        out.append(row)
    return out, stored_as_of
