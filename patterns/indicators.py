"""Rolling maths. Pure Python — every series here is a few hundred points."""
from __future__ import annotations

from collections.abc import Sequence

from data.types import Bar


def closes(bars: Sequence[Bar]) -> list[float]:
    return [b.close for b in bars]


def sma(values: Sequence[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if window <= 0 or len(values) < window:
        return out
    running = sum(values[:window])
    out[window - 1] = running / window
    for i in range(window, len(values)):
        running += values[i] - values[i - window]
        out[i] = running / window
    return out


def true_range(bars: Sequence[Bar]) -> list[float]:
    out: list[float] = []
    for i, b in enumerate(bars):
        if i == 0:
            out.append(b.high - b.low)
            continue
        prev = bars[i - 1].close
        out.append(max(b.high - b.low, abs(b.high - prev), abs(b.low - prev)))
    return out


def atr(bars: Sequence[Bar], window: int = 14) -> list[float | None]:
    return sma(true_range(bars), window)


def atr_pct(bars: Sequence[Bar], window: int = 14) -> list[float | None]:
    a = atr(bars, window)
    return [None if v is None or b.close <= 0 else 100.0 * v / b.close
            for v, b in zip(a, bars)]


def rolling_max(values: Sequence[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        out.append(max(values[lo:i + 1]) if i >= 0 else None)
    return out


def rolling_min(values: Sequence[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        out.append(min(values[lo:i + 1]) if i >= 0 else None)
    return out


def pct_change(values: Sequence[float], periods: int) -> float | None:
    if len(values) <= periods or values[-1 - periods] <= 0:
        return None
    return values[-1] / values[-1 - periods] - 1.0


def percentile_ranks(scores: dict[str, float], lo: int = 1, hi: int = 99) -> dict[str, int]:
    """Map raw scores onto a 1-99 percentile, ties sharing the lower rank."""
    if not scores:
        return {}
    ordered = sorted(scores.items(), key=lambda kv: kv[1])
    n = len(ordered)
    out: dict[str, int] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        frac = i / (n - 1) if n > 1 else 1.0
        rank = int(round(lo + frac * (hi - lo)))
        for k in range(i, j + 1):
            out[ordered[k][0]] = max(lo, min(hi, rank))
        i = j + 1
    return out


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def ema(values: Sequence[float], window: int) -> list[float | None]:
    """Exponential moving average, seeded with the first `window` mean.

    None until there is enough history, like sma, so a caller can never read a
    value that was averaged over fewer bars than it asked for.
    """
    n = len(values)
    out: list[float | None] = [None] * n
    if window <= 0 or n < window:
        return out
    seed = sum(values[:window]) / window
    out[window - 1] = seed
    k = 2.0 / (window + 1.0)
    previous = seed
    for i in range(window, n):
        previous = values[i] * k + previous * (1.0 - k)
        out[i] = previous
    return out
