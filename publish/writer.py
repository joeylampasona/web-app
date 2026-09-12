"""Writes the out/ tree. Local only — wiring R2 or a CDN is a stop condition."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
from typing import Any

from backtest import engine, metrics
from backtest.settings import OPTIONS, BacktestSettings
from catalysts import events as ev
from catalysts import iv as ivmod
from data import classify, settings
from data.market import Market
from patterns import params as param_module
from patterns import scan, stages
from publish import schema
from rankings import breadth, groups, rotation, rs, treemap

VERSION = 1

DISCLAIMER = (
    "A screening and market-analytics tool. Not investment advice. We are not a "
    "registered investment adviser. Historical figures are backtests and are "
    "hypothetical.")

TRADE_STEPS = [
    {"step": 1, "title": "Buy the breakout", "text": "As it pushes through the pivot.",
     "tone": "gain"},
    {"step": 2, "title": "Set a safety net",
     "text": "An automatic exit if it drops about 8% from where you got in.",
     "tone": "loss"},
    {"step": 3, "title": "Lock in \"no loss\"",
     "text": "Once it is up enough, move that net to where you started.", "tone": "gain"},
    {"step": 4, "title": "Ride the trend", "text": "Raise the net as it climbs.",
     "tone": "gain"},
    {"step": 5, "title": "Step off", "text": "When the trend breaks.", "tone": "flat"},
]
TRADE_STEPS_PREFACE = ("Risk is decided before entry — about 1.5% of capital on any one "
                       "trade.")


def _write(path: pathlib.Path, payload: Any) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=False,
                               default=str), encoding="utf-8")
    return path


def _bars_for(market: Market, symbol: str, limit: int) -> list[dict]:
    return [{"time": b.date.isoformat(), "open": b.open, "high": b.high,
             "low": b.low, "close": b.close, "volume": b.volume}
            for b in (market.series.get(symbol) or [])[-limit:]]


def publish(market: Market, bundle: rs.Bundle, result: scan.ScanResult,
            calendar: ev.Calendar, iv_rows: list, diff_payload: dict,
            backtests: dict[str, dict] | None = None,
            out: pathlib.Path | None = None) -> list[pathlib.Path]:
    out = out or settings.out_dir()
    written: list[pathlib.Path] = []
    as_of = market.as_of
    breakout_symbols = result.fresh_breakout_symbols()
    theme_names = classify.theme_names()

    # ---- screens ------------------------------------------------------
    for key, setups in result.screens.items():
        spec = param_module.SCREENS[key]
        grouped = {stage: [s.to_json() for s in setups if s.stage == stage]
                   for stage in stages.ORDER}
        written.append(_write(out / "screens" / f"{key}.json", {
            "screen": key,
            "name": spec.name,
            "description": spec.description,
            "as_of": as_of.isoformat(),
            "total": len(setups),
            "stage_counts": {stage: len(rows) for stage, rows in grouped.items()},
            "stage_labels": stages.LABELS,
            "stage_help": {
                stages.FORMING: "resting before a breakout",
                stages.FRESH: "cleared it in the last 5 sessions",
                stages.CLIMBING: "broke out earlier, still rising",
                stages.PLAYED_OUT: f"{as_of.year} breakouts, stopped or trailed out",
            },
            "setups": grouped,
        }))
    written.append(_write(out / "screens" / "diff.json", diff_payload))

    # ---- breakouts by session ----------------------------------------
    fresh = [s for s in result.all_setups() if s.stage == stages.FRESH]
    seen: dict[str, dict] = {}
    for setup in sorted(fresh, key=lambda s: -(s.breakout_metrics.get(
            "breakout_day_gain_pct") or 0)):
        seen.setdefault(setup.symbol, setup.to_json())
    written.append(_write(out / "breakouts" / f"{as_of.isoformat()}.json", {
        "date": as_of.isoformat(),
        "count": len(seen),
        "metric_set": ["breakout_day_gain_pct", "one_day_gain_pct", "now_vs_pivot_pct",
                       "breakout_volume_multiple", "close_in_range", "rs_rating",
                       "price_vs_50ma_pct"],
        "setups": list(seen.values()),
    }))
    _retain_breakouts(out / "breakouts")
    written.append(_write(out / "breakouts" / "index.json", {
        "dates": sorted(p.stem for p in (out / "breakouts").glob("*.json")
                        if p.stem != "index")[::-1]}))

    # ---- market-wide --------------------------------------------------
    breadth_payload = breadth.compute(market)
    written.append(_write(out / "breadth.json", breadth_payload))
    written.append(_write(out / "rotation.json",
                          rotation.compute(market, bundle, breakout_symbols)))
    written.append(_write(out / "treemap.json",
                          treemap.compute(market, bundle, breakout_symbols)))

    industries = groups.aggregate(market, bundle, "industry", breakout_symbols)
    themes = groups.aggregate(market, bundle, "theme", breakout_symbols)
    written.append(_write(out / "sectors.json", {
        "as_of": as_of.isoformat(),
        "strongest": industries[:12],
        "weakest": list(reversed(industries[-12:])),
        "themes_strongest": themes[:12],
        "themes_weakest": list(reversed(themes[-12:])),
        "heating_cooling": rotation.heating_cooling(industries),
        "themes_heating_cooling": rotation.heating_cooling(themes),
        "sector_etfs": rs.etf_ratings(market),
    }))

    setups_by_symbol: dict[str, list] = {}
    for setup in result.all_setups():
        setups_by_symbol.setdefault(setup.symbol, []).append(setup)

    for row in industries:
        written.append(_write(out / "industries" / f"{row['slug']}.json",
                              _group_payload(row, setups_by_symbol, market, bundle)))
    for row in themes:
        written.append(_write(out / "themes" / f"{row['slug']}.json",
                              _group_payload(row, setups_by_symbol, market, bundle)))

    # ---- stocks -------------------------------------------------------
    bar_limit = int(settings.get("publish.stocks_bars", 260))
    for symbol in market.universe:
        written.append(_write(out / "stocks" / f"{symbol}.json",
                              _stock_payload(market, bundle, symbol, setups_by_symbol,
                                             calendar, bar_limit)))

    # ---- catalysts ----------------------------------------------------
    upcoming = sorted((e for rows in calendar.by_ticker.values() for e in rows
                       if e.date >= as_of), key=lambda e: (e.date, e.ticker))
    written.append(_write(out / "catalysts" / "upcoming.json", {
        "as_of": as_of.isoformat(),
        "count": len(upcoming),
        "owned": sum(1 for e in upcoming if not e.readthrough),
        "readthrough": sum(1 for e in upcoming if e.readthrough),
        "events": [e.to_json(as_of) for e in upcoming],
        "type_labels": ev.TYPE_LABELS,
    }))
    written.append(_write(out / "catalysts" / "high_iv.json", {
        "as_of": as_of.isoformat(),
        "copy": ivmod.COPY,
        "band_labels": ivmod.BAND_LABELS,
        "dots": settings.get("iv.dots", 5),
        "rows": [r.to_json() for r in iv_rows],
    }))

    # ---- learn --------------------------------------------------------
    for key, spec in param_module.SCREENS.items():
        written.append(_write(out / "learn" / f"{key}.json", {
            "screen": key,
            "name": spec.name,
            "shape": spec.shape,
            "description": spec.description,
            "concepts": [c.__dict__ for c in spec.concepts],
            "funnel": param_module.funnel_steps(key),
            "funnel_preface": "Every number below is a dial you can move in Filters.",
            "funnel_callout": {
                "text": "Don't take our word for it — test it on years of data.",
                "cta": "Backtest", "href": "/learn/backtest",
            },
            "params": [p.to_json() for p in spec.params],
            "trade_steps": TRADE_STEPS,
            "trade_steps_preface": TRADE_STEPS_PREFACE,
        }))

    # ---- backtest presets ---------------------------------------------
    written.append(_write(out / "backtest" / "options.json", {
        "options": OPTIONS,
        "defaults": BacktestSettings.defaults().to_json(),
        "years": sorted({d.year for d in market.calendar}),
    }))
    for key, payload in (backtests or {}).items():
        written.append(_write(out / "backtest" / "presets" / f"{key}.json", payload))
    if backtests:
        written.append(_write(out / "backtest" / "presets" / "index.json",
                              {"default_by_screen": {
                                  s: BacktestSettings.parse({"screen": s}).hash()
                                  for s in param_module.SCREEN_KEYS}}))

    # ---- meta ---------------------------------------------------------
    provider = settings.get("data.provider", "polygon")
    meta = {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "provider": provider,
        "data_source": "synthetic_demo" if provider == "synthetic" else "live",
        "data_source_note": (
            "Prices on this build are a deterministic fixture, not real market data. "
            "Tickers and company names are invented." if provider == "synthetic" else ""),
        "universe_count": len(market.universe),
        "survivorship_safe": bool(settings.get("backtest.survivorship_safe", False)),
        "benchmark": market.benchmark,
        "market_wide_breakouts": int(next(
            (c["value"] for c in breadth_payload.get("cards", [])
             if c["key"] == "breakouts"), 0)),
        "screens": [{"key": k, "name": param_module.SCREENS[k].name,
                     "total": len(v), "stages": result.counts(k)}
                    for k, v in result.screens.items()],
        "themes": [{"slug": s, "name": n} for s, n in sorted(theme_names.items())],
        "disclaimer": DISCLAIMER,
    }
    problems = schema.validate(meta)
    meta["schema_valid"] = not problems
    if problems:
        meta["schema_problems"] = problems
    written.append(_write(out / "meta.json", meta))
    return written


def _retain_breakouts(folder: pathlib.Path) -> None:
    keep = int(settings.get("publish.breakouts_retained", 30))
    files = sorted(p for p in folder.glob("*.json") if p.stem != "index")
    for path in files[:-keep] if len(files) > keep else []:
        path.unlink()


def _group_payload(row: dict, setups_by_symbol: dict, market: Market,
                   bundle: rs.Bundle) -> dict:
    members = []
    for symbol in row["symbols"]:
        rating = bundle.now.get(symbol)
        members.append({
            "symbol": symbol,
            "name": market.refs[symbol].name if symbol in market.refs else symbol,
            "rs_rating": rating,
            "rs_change_m1": bundle.change(symbol, "m1"),
            "market_cap": market.caps.get(symbol),
            "industry": market.industries.get(symbol),
            "themes": market.themes.get(symbol, []),
            "screens": sorted({s.screen for s in setups_by_symbol.get(symbol, [])}),
            "stage": next((s.stage for s in setups_by_symbol.get(symbol, [])), None),
        })
    payload = dict(row)
    payload["members_detail"] = members
    return payload


def _stock_payload(market: Market, bundle: rs.Bundle, symbol: str,
                   setups_by_symbol: dict, calendar: ev.Calendar, bar_limit: int) -> dict:
    ref = market.refs.get(symbol)
    setups = setups_by_symbol.get(symbol, [])
    primary = setups[0] if setups else None
    industry = market.industries.get(symbol, "Unclassified")
    themes = market.themes.get(symbol, [])

    def peer_rows(candidates: list[str]) -> list[dict]:
        rows = []
        for peer in candidates:
            if peer == symbol:
                continue
            rating = bundle.now.get(peer)
            rows.append({"symbol": peer,
                         "name": market.refs[peer].name if peer in market.refs else peer,
                         "rs_rating": rating})
        rows.sort(key=lambda r: -(r["rs_rating"] if isinstance(r["rs_rating"], int) else -1))
        return rows[:8]

    same_industry = [s for s in market.universe if market.industries.get(s) == industry]
    same_theme = [s for s in market.universe
                  if set(market.themes.get(s, [])) & set(themes)] if themes else []

    events = calendar.sorted_for(symbol)
    return {
        "symbol": symbol,
        "name": ref.name if ref else symbol,
        "industry": industry,
        "themes": themes,
        "list_date": ref.list_date.isoformat() if ref and ref.list_date else None,
        "as_of": market.as_of.isoformat(),
        "rs_rating": bundle.now.get(symbol),
        "rs_change_m1": bundle.change(symbol, "m1"),
        "market_cap": market.caps.get(symbol),
        "quadrant": (primary.quadrant if primary else
                     rotation.quadrant_for(bundle.now.get(symbol)
                                           if isinstance(bundle.now.get(symbol), int) else None,
                                           bundle.change(symbol, "m1"))),
        "bars": _bars_for(market, symbol, bar_limit),
        "setups": [s.to_json() for s in setups],
        "primary_setup": primary.to_json() if primary else None,
        "base_history": primary.base_history if primary else [],
        "catalyst_roadmap": [e.to_json(market.as_of) for e in events],
        "peers": {"industry": peer_rows(same_industry), "theme": peer_rows(same_theme)},
    }
