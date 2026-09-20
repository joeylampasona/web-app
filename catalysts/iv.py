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
            gamma_out: dict | None = None) -> list[IVRow]:
    """Implied-volatility richness per name, and optionally gamma alongside it.

    `gamma_out`, when given, is filled with one GammaProfile per symbol whose
    chain carried usable open interest. It is an out-parameter rather than a
    second return value because the chain download is the expensive part of
    this stage and both readings come from it: asking for gamma separately
    would fetch every chain twice.
    """
    from catalysts import gamma as gammamod          # noqa: PLC0415 - avoids a cycle
    from data import settings as settingsmod         # noqa: PLC0415

    adapter = adapter or get_adapter()
    rate = float(settingsmod.get("catalysts.risk_free_rate", 0.0) or 0.0)
    rows: list[IVRow] = []
    for symbol in sorted(set(symbols)):
        event: Event | None = calendar.next_owned(symbol)
        if event is None:
            continue                              # rule 3
        try:
            chain = adapter.get_option_chain(symbol)
        except NotImplementedError:
            chain = None
        except Exception:                         # noqa: BLE001
            chain = None
        if chain is None:
            continue
        # Before the IV-specific tests below. A chain whose expiries do not
        # bracket the event still has open interest at strikes, and that is a
        # separate reading from whether the event is priced richly.
        if gamma_out is not None:
            found = gammamod.profile(chain, calendar.as_of, rate)
            if found is not None:
                gamma_out[symbol] = found
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
