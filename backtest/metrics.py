"""Result metrics, the provisional flags, and the sentence that explains them."""
from __future__ import annotations

import datetime as dt

from backtest.engine import RunOutput
from data import settings as cfg
from patterns.indicators import mean, median

PROVISIONAL_LINE = ("These figures are under a methodology review and will be revised.")

SURVIVORSHIP_LINE = (
    "Our data provider's free tier carries no delisted companies, so this test only "
    "ever saw names that survived to today. Every return below is flattered by that.")

TOOLTIPS = {
    "end_capital": "What the starting capital would have become, after costs, if every "
                   "rule above had been followed without exception.",
    "multiple": "Ending capital divided by starting capital.",
    "cagr": "The single yearly rate that would turn the starting capital into the "
            "ending capital over this period.",
    "best_year": "The calendar year with the largest gain, and what it was.",
    "worst_year": "The calendar year with the largest loss, and what it was.",
    "max_drawdown": "The deepest fall from a peak in the account to the low that "
                    "followed it, before a new peak was made.",
    "won_pct": "Share of closed trades that made money after costs.",
    "avg_gain": "Average return of the trades that made money.",
    "avg_loss": "Average return of the trades that lost money.",
    "mean": "Average return across every closed trade, winners and losers together.",
    "median": "The middle trade: half did better, half did worse.",
    "trades": "Closed trades over the period.",
    "passed_up": "Signals that qualified on the day but were not taken because the "
                 "maximum number of positions was already held.",
    "strong_market_pct": "Share of sessions where the benchmark closed above its "
                         "200-day average.",
    "benchmark": "Buying the benchmark on the first session and holding to the last.",
}


def _yearly(curve: list[tuple[dt.date, float]]) -> list[dict]:
    if not curve:
        return []
    out: list[dict] = []
    by_year: dict[int, list[tuple[dt.date, float]]] = {}
    for day, equity in curve:
        by_year.setdefault(day.year, []).append((day, equity))
    prior_close = curve[0][1]
    for year in sorted(by_year):
        rows = by_year[year]
        start = prior_close
        end = rows[-1][1]
        out.append({"year": year,
                    "return_pct": round(100.0 * (end / start - 1.0), 2) if start else 0.0,
                    "start_equity": round(start, 2), "end_equity": round(end, 2)})
        prior_close = end
    return out


def _max_drawdown(curve: list[tuple[dt.date, float]]) -> float:
    peak = 0.0
    worst = 0.0
    for _, equity in curve:
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, equity / peak - 1.0)
    return 100.0 * worst


def summarise(result: RunOutput) -> dict:
    config = result.settings
    curve = result.equity_curve
    start = float(config.starting_capital)
    end = curve[-1][1] if curve else start
    years = ((curve[-1][0] - curve[0][0]).days / 365.25) if len(curve) > 1 else 0.0
    cagr = (100.0 * ((end / start) ** (1.0 / years) - 1.0)) if years > 0.5 and start > 0 else None

    closed = result.trades
    returns = [t.return_pct for t in closed]
    gains = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    yearly = _yearly(curve)
    best = max(yearly, key=lambda r: r["return_pct"]) if yearly else None
    worst = min(yearly, key=lambda r: r["return_pct"]) if yearly else None

    survivorship_safe = bool(cfg.get("backtest.survivorship_safe", False))
    provisional = (not survivorship_safe) and bool(cfg.get("backtest.provisional_when_unsafe", True))
    strong_pct = (100.0 * result.strong_sessions / result.total_sessions
                  if result.total_sessions else 0.0)

    def metric(key: str, value, label: str, unit: str = "", flagged: bool | None = None):
        return {"key": key, "label": label, "value": value, "unit": unit,
                "help": TOOLTIPS.get(key, ""),
                "provisional": provisional if flagged is None else flagged}

    metrics = [
        metric("cagr", None if cagr is None else round(cagr, 2), "CAGR", "%"),
        metric("best_year", best["return_pct"] if best else None,
               f"Best year ({best['year']})" if best else "Best year", "%"),
        metric("worst_year", worst["return_pct"] if worst else None,
               f"Worst year ({worst['year']})" if worst else "Worst year", "%"),
        metric("max_drawdown", round(_max_drawdown(curve), 2), "Worst fall", "%"),
        metric("won_pct", round(100.0 * len(gains) / len(closed), 2) if closed else None,
               "Won", "%"),
        metric("avg_gain", round(mean(gains), 2) if gains else None, "Average gain", "%"),
        metric("avg_loss", round(mean(losses), 2) if losses else None, "Average loss", "%"),
        metric("mean", round(mean(returns), 2) if returns else None, "Mean", "%"),
        metric("median", round(median(returns), 2) if returns else None, "Median", "%"),
        metric("trades", len(closed), "Trades", ""),
        metric("passed_up", result.passed_up, "Trades passed up", "",
               flagged=provisional or bool(result.notes)),
        metric("strong_market_pct", round(strong_pct, 1), "Period in a strong market",
               "%", flagged=False),
    ]

    gross = mean([t.gross_return_pct for t in closed]) if closed else 0.0
    net = mean(returns) if closed else 0.0

    sentence = _sentence(config, years, start, end, len(closed), result.passed_up, strong_pct)

    return {
        "settings": config.to_json(),
        "hash": config.hash(),
        "provisional": provisional,
        "provisional_line": PROVISIONAL_LINE if provisional else "",
        "survivorship_safe": survivorship_safe,
        "survivorship_line": "" if survivorship_safe else SURVIVORSHIP_LINE,
        "notes": result.notes,
        "starting_capital": round(start, 2),
        "ending_capital": round(end, 2),
        "multiple": round(end / start, 2) if start else None,
        "years": round(years, 2),
        "metrics": metrics,
        "summary": sentence,
        "yearly": yearly,
        "gross_mean_return_pct": round(gross, 2),
        "net_mean_return_pct": round(net, 2),
        "cost_bps_round_trip": cfg.get("backtest.cost_bps_round_trip", 10),
        "benchmark": {
            "symbol": cfg.get("backtest.benchmark", "SPY"),
            "buy_and_hold_return_pct": (None if result.benchmark_return_pct is None
                                        else round(result.benchmark_return_pct, 2)),
            "help": TOOLTIPS["benchmark"],
        },
        "trades": [t.to_json() for t in sorted(closed, key=lambda t: t.entry_date)],
    }


def _sentence(config, years: float, start: float, end: float, trades: int,
              passed: int, strong_pct: float) -> str:
    span = f"{years:.1f} years" if years >= 1 else f"{years * 12:.0f} months"
    return (
        f"Over {span}, ${start:,.0f} became ${end:,.0f} on {trades} trades, "
        f"holding at most {config.positions} at a time and cutting a loser at "
        f"{config.stop_pct:g}%. {passed} more signals qualified and were passed up "
        f"because the book was already full. "
        f"{strong_pct:.0f}% of the period was a strong market by this test's own "
        f"definition — the benchmark above its 200-day average."
    )


def render(summary: dict) -> str:
    lines = []
    if summary["provisional"]:
        lines.append(f"  PROVISIONAL — {summary['provisional_line']}")
        for chunk in _wrap(summary["survivorship_line"], 88):
            lines.append(f"  {chunk}")
        lines.append("")
    lines.append(f"  ${summary['starting_capital']:,.0f} → ${summary['ending_capital']:,.0f}"
                 f"   ({summary['multiple']}×  over {summary['years']} years)")
    lines.append("")
    for m in summary["metrics"]:
        value = "—" if m["value"] is None else f"{m['value']:,}{m['unit']}"
        lines.append(f"  {m['label']:<30}{value:>14}"
                     + ("   PROVISIONAL" if m["provisional"] else ""))
    bench = summary["benchmark"]
    if bench["buy_and_hold_return_pct"] is not None:
        lines.append(f"  {'Buy and hold ' + bench['symbol']:<30}"
                     f"{bench['buy_and_hold_return_pct']:>13,.2f}%")
    lines.append("")
    lines.append(f"  Gross mean trade {summary['gross_mean_return_pct']:+.2f}%,"
                 f" net of {summary['cost_bps_round_trip']}bps round trip"
                 f" {summary['net_mean_return_pct']:+.2f}%")
    lines.append("")
    for chunk in _wrap(summary["summary"], 88):
        lines.append(f"  {chunk}")
    for note in summary["notes"]:
        lines.append("")
        for chunk in _wrap(note, 88):
            lines.append(f"  {chunk}")
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    words, line, out = text.split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out
