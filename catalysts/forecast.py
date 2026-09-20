"""Analyst price targets and estimates.

THIS IS SOMEBODY ELSE'S OPINION, AND THAT MAKES IT DIFFERENT
-----------------------------------------------------------

Everything else this site publishes is either computed from prices it holds or
copied from a filing somebody signed. A price target is neither. It is a number
an analyst chose, at a firm with its own business, and the consensus of them is
an average of choices rather than a measurement of anything.

That does not make it worthless — what the sell side expects is a real fact
about the market, and it moves prices — but it does mean it has to be presented
the way the news feed is: attributed, dated, counted, and never in the site's
own voice. So every figure here travels with the number of analysts behind it,
and the page says whose view it is.

It is also the one thing on this site that is explicitly a forecast, on a site
whose disclaimer says a pattern is not a prediction. The resolution is to
report the forecast as a fact about analysts rather than as a fact about the
company: "61 analysts average $333" is checkable and true; "$333 is where this
is going" is not something anyone can know.

COST
----

Per-ticker, from the same undocumented Yahoo endpoint as the earnings dates,
with the same rate limit and the same failure mode. So it uses the same
answer: a cache, a freshness window, and a nightly pass that only asks about
names whose data has aged out. Estimates move slowly — an analyst revising a
target is news precisely because it is uncommon — so a week is generous.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence

log = logging.getLogger(__name__)

#: How long a stored forecast is trusted. Long, because revisions are rare and
#: the request budget is the binding constraint.
FRESH_DAYS = 7

#: Periods Yahoo reports, in the order a reader wants them.
PERIOD_LABELS = {
    "0q": "This quarter",
    "+1q": "Next quarter",
    "0y": "This year",
    "+1y": "Next year",
}
PERIOD_ORDER = ["0q", "+1q", "0y", "+1y"]


def _yf():
    try:
        import yfinance                           # noqa: PLC0415
        return yfinance
    except Exception as exc:                      # noqa: BLE001
        log.warning("yfinance unavailable (%s) — forecasts will be empty", exc)
        return None


def _number(value) -> float | None:
    """A finite float, or None. Yahoo sends NaN, None and strings freely."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def _frame_rows(frame) -> list[dict]:
    """A DataFrame from yfinance's _get_periodic_df, as plain rows.

    Written to survive the frame being empty, being None, or having its period
    in the index rather than a column — all three have been seen from this
    endpoint and none of them is documented.
    """
    if frame is None:
        return []
    try:
        if getattr(frame, "empty", True):
            return []
        records = frame.reset_index().to_dict("records")
    except Exception as exc:                      # noqa: BLE001
        log.debug("estimate frame unreadable: %s", exc)
        return []

    out: list[dict] = []
    for record in records:
        period = str(record.get("period") or record.get("index") or "").strip()
        if period not in PERIOD_LABELS:
            continue
        out.append({
            "period": period,
            "label": PERIOD_LABELS[period],
            "avg": _number(record.get("avg")),
            "low": _number(record.get("low")),
            "high": _number(record.get("high")),
            "analysts": _number(record.get("numberOfAnalysts")),
            "year_ago": _number(record.get("yearAgoEps")
                                if "yearAgoEps" in record else record.get("yearAgoRevenue")),
            "growth": _number(record.get("growth")),
        })
    out.sort(key=lambda row: PERIOD_ORDER.index(row["period"]))
    return out


def fetch_one(symbol: str) -> dict | None:
    """Targets and estimates for one name. None when nothing usable came back.

    Every branch degrades to None rather than raising. This endpoint is
    undocumented and unversioned: it has changed shape before and will again,
    and a forecast panel going quiet is a smaller problem than a nightly run
    that stops.
    """
    yf = _yf()
    if yf is None:
        return None
    try:
        ticker = yf.Ticker(symbol)
    except Exception as exc:                      # noqa: BLE001
        log.debug("ticker construction failed for %s: %s", symbol, exc)
        return None

    targets: dict = {}
    try:
        raw = ticker.analyst_price_targets or {}
        targets = {key: _number(raw.get(key))
                   for key in ("current", "low", "mean", "median", "high")}
    except Exception as exc:                      # noqa: BLE001
        log.debug("price targets failed for %s: %s", symbol, exc)

    eps = revenue = []
    try:
        eps = _frame_rows(ticker.earnings_estimate)
    except Exception as exc:                      # noqa: BLE001
        log.debug("earnings estimate failed for %s: %s", symbol, exc)
    try:
        revenue = _frame_rows(ticker.revenue_estimate)
    except Exception as exc:                      # noqa: BLE001
        log.debug("revenue estimate failed for %s: %s", symbol, exc)

    ratings = _ratings(ticker, symbol)

    has_target = any(v is not None for k, v in targets.items() if k != "current")
    if not (has_target or eps or revenue or ratings):
        return None

    mean = targets.get("mean")
    current = targets.get("current")
    return {
        "symbol": symbol,
        "targets": targets,
        # Upside is derived here rather than in the page so the page cannot
        # compute it from a stale price beside a fresh target.
        "upside_pct": (round(100.0 * (mean / current - 1.0), 2)
                       if mean and current else None),
        "eps": eps,
        "revenue": revenue,
        "ratings": ratings,
        "analysts": _analyst_count(eps),
    }


def _ratings(ticker, symbol: str) -> dict | None:
    """Buy/hold/sell counts, if the endpoint offers them."""
    try:
        frame = ticker.recommendations_summary
    except Exception as exc:                      # noqa: BLE001
        log.debug("recommendations failed for %s: %s", symbol, exc)
        return None
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        row = frame.reset_index().to_dict("records")[0]
    except Exception:                             # noqa: BLE001
        return None
    keys = ("strongBuy", "buy", "hold", "sell", "strongSell")
    counts = {key: int(_number(row.get(key)) or 0) for key in keys}
    return counts if sum(counts.values()) else None


def _analyst_count(eps_rows: list[dict]) -> int | None:
    """The largest analyst count across the reported periods.

    Yahoo reports a count per period and they differ; the page wants one
    number, and the largest is the honest one to show beside "analysts cover
    this name" — a period with fewer is a period some of them did not forecast,
    not evidence that the coverage is smaller.
    """
    counts = [int(row["analysts"]) for row in eps_rows
              if row.get("analysts") is not None]
    return max(counts) if counts else None


# ---------------------------------------------------------------- cache

def store(conn, rows: dict[str, dict]) -> int:
    """Keep what arrived. Returns rows written."""
    import json                                   # noqa: PLC0415

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    written = 0
    for symbol, payload in rows.items():
        conn.execute(
            "INSERT OR REPLACE INTO forecasts(symbol, payload, fetched_at)"
            " VALUES (?,?,?)",
            (symbol.upper(), json.dumps(payload, separators=(",", ":")), now))
        written += 1
    conn.commit()
    return written


def stale_symbols(conn, symbols: Sequence[str],
                  fresh_days: int = FRESH_DAYS) -> list[str]:
    """The names worth asking about tonight."""
    cutoff = (dt.datetime.now(dt.timezone.utc)
              - dt.timedelta(days=fresh_days)).isoformat(timespec="seconds")
    fresh = {r[0] for r in conn.execute(
        "SELECT symbol FROM forecasts WHERE fetched_at >= ?", (cutoff,))}
    return [s for s in symbols if s.upper() not in fresh]


def load(conn, symbols: Sequence[str]) -> dict[str, dict]:
    """Stored forecasts, with the age of each so the page can say how old."""
    import json                                   # noqa: PLC0415

    wanted = {s.upper() for s in symbols}
    out: dict[str, dict] = {}
    for row in conn.execute("SELECT symbol, payload, fetched_at FROM forecasts"):
        symbol = row[0]
        if symbol not in wanted:
            continue
        try:
            payload = json.loads(row[1])
        except (TypeError, ValueError):
            continue
        payload["fetched_at"] = row[2]
        out[symbol] = payload
    return out


def fetch(conn, symbols: Sequence[str], limit: int | None = None,
          notice=None) -> tuple[int, int]:
    """Ask about the names whose forecasts have aged out. Returns (asked, kept).

    `limit` caps how many are asked for in one night. The universe divided by
    the freshness window is the steady-state rate, but the first run has no
    cache at all and would otherwise try every name in one pass — which is how
    the earnings scrape got itself rate-limited before it was given a cache.
    """
    from data import settings                    # noqa: PLC0415
    if settings.get("data.provider") == "synthetic":
        return _synthetic(conn, symbols, notice)

    ask = stale_symbols(conn, symbols)
    if limit is not None:
        ask = ask[:limit]
    if notice:
        notice(f"forecasts: {len(symbols) - len(ask):,} names still fresh, "
               f"asking about {len(ask):,}.")
    if not ask:
        return 0, 0

    found: dict[str, dict] = {}
    for symbol in ask:
        payload = fetch_one(symbol)
        if payload is not None:
            found[symbol] = payload
    kept = store(conn, found) if found else 0
    if notice:
        if kept:
            notice(f"forecasts: {kept:,} of {len(ask):,} came back with data.")
        else:
            # Loud, because the failure mode is a section that renders empty
            # while every counter reads fine.
            notice(f"forecasts: asked about {len(ask):,} names and NONE returned "
                   f"usable data. Either the endpoint changed shape or it is "
                   f"refusing us — the forecast panel will be blank.")
    return len(ask), kept


def _synthetic(conn, symbols: Sequence[str], notice=None) -> tuple[int, int]:
    """Plausible coverage for the offline fixture.

    The fourth surface on this site that could not be checked offline, after
    the option spot, the volume spikes and the insider filings. Yahoo is not
    reachable from a fixture build by design, so without this the forecast
    panel would render empty on every local run and the only way to see it
    would be to ship it and wait for a nightly.

    Shaped like real coverage: most names have none at all, the ones that do
    have a wide spread between the low and high target, and the consensus sits
    nearer the middle than the extremes.
    """
    import random                                  # noqa: PLC0415

    rng = random.Random(20260921)
    found: dict[str, dict] = {}
    for symbol in symbols:
        if rng.random() > 0.35:                    # most names are uncovered
            continue
        current = round(rng.uniform(8.0, 900.0), 2)
        analysts = rng.randint(3, 58)
        mean = current * rng.uniform(0.82, 1.55)
        low = mean * rng.uniform(0.45, 0.85)
        high = mean * rng.uniform(1.2, 2.4)
        eps_base = max(round(current * rng.uniform(0.01, 0.07), 2), 0.05)
        rows, rev_rows = [], []
        # Quarters and years are not interchangeable. Treating them as one
        # ascending series gave the fixture "this year" below "next quarter"
        # and revenue that went 156B, 953B, 344B — numbers no company could
        # report, on a panel whose whole job is to look like a real one.
        rev_base = current * rng.uniform(4e6, 9e8)
        annual_growth = rng.uniform(1.05, 1.45)
        scale = {"0q": 1.0, "+1q": rng.uniform(1.02, 1.18),
                 "0y": 4.0, "+1y": 4.0 * annual_growth}
        for period in PERIOD_ORDER:
            grow = scale[period]
            avg = round(eps_base * grow, 2)
            rows.append({
                "period": period, "label": PERIOD_LABELS[period],
                "avg": avg, "low": round(avg * 0.82, 2), "high": round(avg * 1.21, 2),
                "analysts": float(max(analysts - rng.randint(0, 6), 1)),
                "year_ago": round(avg / rng.uniform(1.05, 1.6), 2),
                "growth": round(rng.uniform(-0.15, 0.6), 4),
            })
            rev = rev_base * grow
            rev_rows.append({
                "period": period, "label": PERIOD_LABELS[period],
                "avg": round(rev, 0), "low": round(rev * 0.9, 0),
                "high": round(rev * 1.12, 0),
                "analysts": float(max(analysts - rng.randint(0, 8), 1)),
                "year_ago": round(rev / rng.uniform(1.05, 1.7), 0),
                "growth": round(rng.uniform(-0.1, 0.7), 4),
            })
        strong = rng.randint(0, analysts)
        rest = analysts - strong
        buy = rng.randint(0, rest)
        rest -= buy
        hold = rng.randint(0, rest)
        found[symbol] = {
            "symbol": symbol,
            "targets": {"current": current, "low": round(low, 2),
                        "mean": round(mean, 2),
                        "median": round((mean + low) / 2 + (high - mean) / 6, 2),
                        "high": round(high, 2)},
            "upside_pct": round(100.0 * (mean / current - 1.0), 2),
            "eps": rows, "revenue": rev_rows,
            "ratings": {"strongBuy": strong, "buy": buy, "hold": hold,
                        "sell": max(rest - hold, 0), "strongSell": 0},
            "analysts": analysts,
        }
    kept = store(conn, found) if found else 0
    if notice:
        notice(f"forecasts: {kept:,} names covered (fixture).")
    return len(found), kept
