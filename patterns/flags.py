"""Cautions. A flag is never a reason on its own — it is context on the chart."""
from __future__ import annotations

from data.types import Bar
from patterns.indicators import mean

SQUAT_LOOKBACK = 5
POKE_LOOKBACK = 10
SQUAT_VOLUME_MULTIPLE = 1.5
SQUAT_CLOSE_IN_RANGE = 0.40


def close_in_range(bar: Bar) -> float:
    span = bar.high - bar.low
    if span <= 0:
        return 0.5
    return max(0.0, min(1.0, (bar.close - bar.low) / span))


def detect(bars: list[Bar], pivot: float) -> list[str]:
    out: list[str] = []
    if not bars or pivot <= 0:
        return out
    volumes = [b.volume for b in bars[-50:]]
    normal = mean(volumes) or 1.0

    for bar in bars[-SQUAT_LOOKBACK:]:
        if (bar.high >= pivot * 0.995
                and bar.volume >= normal * SQUAT_VOLUME_MULTIPLE
                and close_in_range(bar) <= SQUAT_CLOSE_IN_RANGE):
            out.append("squat")
            break

    for bar in bars[-POKE_LOOKBACK:]:
        if bar.high > pivot and bar.close <= pivot:
            out.append("failed_poke")
            break
    return out


DESCRIPTIONS = {
    "squat": "Price reached the pivot on heavy volume and closed in the lower part of "
             "the day's range. Sellers met the move.",
    "failed_poke": "Price pushed above the pivot during a session in the last two weeks "
                   "and closed back underneath it.",
}
