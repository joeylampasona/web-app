"""Run every detector over the universe, stage the results, and diff the day."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from data import store
from data.market import Market
from patterns import stages
from patterns.detectors import DETECTORS, Series, Setup
from patterns.params import SCREEN_KEYS, Params
from rankings.rotation import quadrant_for
from rankings.rs import Bundle

STATE_KEY = "scan_state"


@dataclass
class ScanResult:
    as_of: dt.date
    screens: dict[str, list[Setup]] = field(default_factory=dict)
    diff: dict = field(default_factory=dict)

    def counts(self, screen: str) -> dict[str, int]:
        out = {s: 0 for s in stages.ORDER}
        for setup in self.screens.get(screen, []):
            out[setup.stage] = out.get(setup.stage, 0) + 1
        return out

    def fresh_breakout_symbols(self) -> set[str]:
        """Names that cleared a level UPWARD in the last few sessions.

        Short screens are excluded. Their fresh bucket holds names that broke
        DOWN through a level, and this set feeds the home page's "cleared a
        pivot" count, the market-wide breakout tally and the breakouts-by-day
        file. Letting a bear flag in would have each of those report a falling
        stock as a breakout.
        """
        return {s.symbol for setups in self.screens.values() for s in setups
                if s.stage == stages.FRESH and s.direction != stages.SHORT}

    def fresh_breakdown_symbols(self) -> set[str]:
        """The other half: names that lost a level in the last few sessions."""
        return {s.symbol for setups in self.screens.values() for s in setups
                if s.stage == stages.FRESH and s.direction == stages.SHORT}

    def all_setups(self) -> list[Setup]:
        return [s for setups in self.screens.values() for s in setups]


def _series_for(market: Market, bundle: Bundle, symbol: str) -> Series:
    ref = market.refs.get(symbol)
    return Series(
        symbol=symbol,
        bars=market.series.get(symbol) or [],
        rs_rating=bundle.now.get(symbol, "not ranked yet"),
        list_date=ref.list_date if ref else None,
        name=ref.name if ref else symbol,
    )


def run(market: Market, bundle: Bundle,
        overrides: dict[str, dict[str, Any]] | None = None,
        screens: list[str] | None = None) -> ScanResult:
    result = ScanResult(as_of=market.as_of)
    overrides = overrides or {}
    for key in (screens or SCREEN_KEYS):
        params = Params(key, overrides.get(key))
        detector = DETECTORS[key]
        found: list[Setup] = []
        for symbol in market.universe:
            setup = detector(_series_for(market, bundle, symbol), params)
            if setup is None:
                continue
            rating = bundle.now.get(symbol)
            setup.quadrant = quadrant_for(rating if isinstance(rating, int) else None,
                                          bundle.change(symbol, "m1"))
            setup.themes = market.themes.get(symbol, [])
            setup.industry = market.industries.get(symbol, "Unclassified")
            found.append(setup)
        found.sort(key=lambda s: -(s.rs_rating if isinstance(s.rs_rating, int) else -1))
        result.screens[key] = found
    return result


# ---------------------------------------------------------------- the diff

def _state_from(result: ScanResult) -> dict[str, dict[str, str]]:
    return {key: {s.symbol: s.stage for s in setups}
            for key, setups in result.screens.items()}


def diff(conn: sqlite3.Connection, result: ScanResult, persist: bool = True) -> dict:
    """What changed since the last scan: broke out, newly forming, and what left."""
    previous_raw = store.get_kv(conn, STATE_KEY, "")
    previous: dict[str, dict[str, str]] = json.loads(previous_raw) if previous_raw else {}
    current = _state_from(result)

    out: dict[str, Any] = {"as_of": result.as_of.isoformat(),
                           "first_run": not previous, "screens": {}}
    for key, now in current.items():
        before = previous.get(key, {})
        broke_out = [s.symbol for s in result.screens[key]
                     if s.stage == stages.FRESH and before.get(s.symbol) != stages.FRESH]
        newly_forming = [sym for sym, stage in now.items()
                         if stage == stages.FORMING and sym not in before]
        left = []
        for sym, stage in before.items():
            if sym in now:
                if now[sym] != stage:
                    left.append({"symbol": sym, "reason": f"moved to {now[sym]}",
                                 "from": stage, "to": now[sym]})
                continue
            left.append({"symbol": sym, "from": stage, "to": None,
                         "reason": "no longer passes this screen's filters"})
        out["screens"][key] = {
            "broke_out_today": sorted(broke_out),
            "newly_forming": sorted(newly_forming),
            "left": sorted(left, key=lambda r: r["symbol"]),
            "total": len(now),
        }
    if persist:
        store.set_kv(conn, STATE_KEY, json.dumps(current, sort_keys=True))
    result.diff = out
    return out
