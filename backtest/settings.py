"""The settings table, validated. Changing this list is a stop condition."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from data import settings as cfg
from patterns.params import SCREENS

OPTIONS: dict[str, dict] = {
    "screen": {"label": "Screen", "control": "dropdown",
               "options": [{"value": k, "label": s.name} for k, s in SCREENS.items()]},
    "enter": {"label": "Enter", "control": "segmented",
              "options": [{"value": "breakout_close", "label": "Breakout close"},
                          {"value": "at_pivot", "label": "At the pivot"}]},
    "positions": {"label": "Positions (max concurrent)", "control": "segmented",
                  "options": [{"value": v, "label": str(v)} for v in (3, 5, 8, 10)]},
    "stop_pct": {"label": "Cut a loser at", "control": "segmented",
                 "options": [{"value": v, "label": f"{v}%"} for v in (7, 8, 10)]},
    "exit_rule": {"label": "Exit winners by", "control": "segmented",
                  "options": [{"value": "trail_50d", "label": "Trail 50-day"},
                              {"value": "trail_30w", "label": "Trail 30-week"},
                              {"value": "take_25", "label": "Take +25%"}]},
    "risk_pct": {"label": "Risk per trade", "control": "segmented",
                 "options": [{"value": v, "label": f"{v}%"} for v in (1, 1.5, 2)]},
    "skip_weak_markets": {"label": "Skip weak markets", "control": "segmented",
                          "options": [{"value": True, "label": "On"},
                                      {"value": False, "label": "Off"}]},
    "skip_earnings_7d": {"label": "Skip earnings within 7 days", "control": "segmented",
                         "options": [{"value": True, "label": "On"},
                                     {"value": False, "label": "Off"}]},
    "period": {"label": "Period", "control": "segmented", "options": []},
    "starting_capital": {"label": "Starting capital", "control": "number",
                         "min": 1000, "max": 100_000_000, "step": 1000},
}


@dataclass
class BacktestSettings:
    screen: str = "vcp"
    enter: str = "breakout_close"
    positions: int = 5
    stop_pct: float = 8.0
    exit_rule: str = "trail_50d"
    risk_pct: float = 1.5
    skip_weak_markets: bool = True
    skip_earnings_7d: bool = True
    period: str = "all"
    starting_capital: float = 100_000.0

    @classmethod
    def defaults(cls) -> "BacktestSettings":
        return cls(**(cfg.get("backtest.defaults", {}) or {}))

    @classmethod
    def parse(cls, payload: dict) -> "BacktestSettings":
        base = asdict(cls.defaults())
        for key, value in (payload or {}).items():
            if key in base and value is not None:
                base[key] = value
        out = cls(**base)
        out.validate()
        return out

    def validate(self) -> None:
        def allowed(key: str) -> list:
            return [o["value"] for o in OPTIONS[key]["options"]]
        if self.screen not in SCREENS:
            raise ValueError(f"unknown screen {self.screen!r}")
        for key in ("enter", "positions", "exit_rule"):
            if getattr(self, key) not in allowed(key):
                raise ValueError(f"{key} must be one of {allowed(key)}")
        if float(self.stop_pct) not in [float(v) for v in allowed("stop_pct")]:
            raise ValueError("stop_pct must be one of 7, 8, 10")
        if float(self.risk_pct) not in [float(v) for v in allowed("risk_pct")]:
            raise ValueError("risk_pct must be one of 1, 1.5, 2")
        if self.starting_capital <= 0:
            raise ValueError("starting capital must be positive")
        if self.period != "all" and not str(self.period).isdigit():
            raise ValueError("period must be 'all' or a four-digit year")

    def position_size(self, equity: float) -> float:
        """Risk budget divided by the distance to the stop."""
        risk = equity * float(self.risk_pct) / 100.0
        return risk / (float(self.stop_pct) / 100.0)

    def to_json(self) -> dict:
        return asdict(self)

    def hash(self) -> str:
        payload = json.dumps(self.to_json(), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
