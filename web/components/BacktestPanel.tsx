"use client";

import { useMemo, useState } from "react";
import { money, signed } from "@/lib/format";
import type { BacktestSummary } from "@/lib/types";
import { ProvisionalBadge } from "./Badges";
import { PriceChange } from "./PriceChange";
import { Tooltip } from "./Tooltip";

type Options = Record<string, {
  label: string; control: string;
  options?: { value: string | number | boolean; label: string }[];
  min?: number; max?: number; step?: number;
}>;

type Settings = Record<string, string | number | boolean>;

const ORDER = ["screen", "enter", "positions", "stop_pct", "exit_rule", "risk_pct",
               "skip_weak_markets", "skip_earnings_7d", "period", "starting_capital"];

export function BacktestPanel({
  options, defaults, years, initial,
}: {
  options: Options;
  defaults: Settings;
  years: number[];
  initial: BacktestSummary | null;
}) {
  const [tab, setTab] = useState<"settings" | "result" | "trades">(
    initial ? "result" : "settings");
  const [settings, setSettings] = useState<Settings>(defaults);
  const [result, setResult] = useState<BacktestSummary | null>(initial);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [yearFilter, setYearFilter] = useState<number | null>(null);

  const periodOptions = useMemo(
    () => [{ value: "all", label: "All" },
           ...years.map((year) => ({ value: String(year), label: String(year) }))],
    [years],
  );

  const positionSize = useMemo(() => {
    const risk = Number(settings.risk_pct ?? 1.5) / 100;
    const stop = Number(settings.stop_pct ?? 8) / 100;
    const capital = Number(settings.starting_capital ?? 100000);
    return stop > 0 ? (capital * risk) / stop : 0;
  }, [settings]);

  const runScan = async () => {
    setRunning(true);
    setError("");
    try {
      const response = await fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      const payload = await response.json();
      if (!response.ok) {
        setError(payload.error ?? "That run did not complete.");
      } else {
        setResult(payload as BacktestSummary);
        setYearFilter(null);
        setTab("result");
      }
    } catch {
      setError("That run did not complete.");
    } finally {
      setRunning(false);
    }
  };

  const trades = result
    ? result.trades.filter((t) => yearFilter === null ||
        Number(t.entry_date.slice(0, 4)) === yearFilter)
    : [];

  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      {result?.provisional && (
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          <ProvisionalBadge />
          <p className="footnote muted" style={{ margin: 0 }}>{result.provisional_line}</p>
          <p className="caption dim" style={{ margin: 0 }}>{result.survivorship_line}</p>
        </div>
      )}

      <div className="row" style={{ gap: 0 }}>
        {(["settings", "result", "trades"] as const).map((key, index) => (
          <button
            key={key}
            type="button"
            className="control footnote grow"
            aria-pressed={tab === key}
            style={{
              borderRadius: index === 0 ? "var(--radius) 0 0 var(--radius)"
                : index === 2 ? "0 var(--radius) var(--radius) 0" : 0,
              marginLeft: index ? -1 : 0,
            }}
            onClick={() => setTab(key)}
          >
            {key === "trades" ? "The trades" : key[0].toUpperCase() + key.slice(1)}
          </button>
        ))}
      </div>

      {tab === "settings" && (
        <div className="stack">
          {ORDER.filter((key) => options[key]).map((key) => {
            const spec = options[key];
            const choices = key === "period" ? periodOptions : spec.options ?? [];
            if (spec.control === "number") {
              return (
                <label key={key} className="stack" style={{ gap: "var(--gap-xs)" }}>
                  <span className="footnote muted">{spec.label}</span>
                  <input
                    className="control"
                    style={{ background: "var(--surface-2)", justifyContent: "flex-start" }}
                    inputMode="numeric"
                    value={String(settings[key] ?? "")}
                    onChange={(event) =>
                      setSettings({ ...settings, [key]: Number(event.target.value || 0) })}
                  />
                </label>
              );
            }
            return (
              <div key={key} className="stack" style={{ gap: "var(--gap-xs)" }}>
                <span className="footnote muted">{spec.label}</span>
                {spec.control === "dropdown" ? (
                  <select
                    className="control"
                    style={{ background: "var(--surface-2)" }}
                    value={String(settings[key])}
                    onChange={(event) =>
                      setSettings({ ...settings, [key]: event.target.value })}
                  >
                    {choices.map((choice) => (
                      <option key={String(choice.value)} value={String(choice.value)}>
                        {choice.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="row wrap" style={{ gap: 0 }}>
                    {choices.map((choice, index) => {
                      const selected = String(settings[key]) === String(choice.value);
                      return (
                        <button
                          key={String(choice.value)}
                          type="button"
                          className="control footnote"
                          aria-pressed={selected}
                          style={{
                            borderRadius: index === 0 ? "var(--radius) 0 0 var(--radius)"
                              : index === choices.length - 1
                                ? "0 var(--radius) var(--radius) 0" : 0,
                            marginLeft: index ? -1 : 0,
                          }}
                          onClick={() =>
                            setSettings({ ...settings, [key]: choice.value as never })}
                        >
                          {choice.label}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          <button type="button" className="control primary" onClick={runScan}
                  disabled={running}>
            {running ? "Running…" : "Run scan"}
          </button>
          <p className="footnote muted" style={{ margin: 0 }}>
            At {String(settings.risk_pct)}% risk with a {String(settings.stop_pct)}% stop,
            each position is about <span className="num">{money(positionSize)}</span>.
          </p>
          {error && <p className="footnote" style={{ color: "var(--warn)" }}>{error}</p>}
        </div>
      )}

      {tab === "result" && result && (
        <div className="stack" style={{ gap: "var(--pad-lg)" }}>
          <div className="card">
            <div className="footnote muted">Starting → ending capital</div>
            <div className="row wrap" style={{ gap: "var(--gap-md)", alignItems: "baseline" }}>
              <span className="num" style={{ fontSize: "var(--size-hero)" }}>
                {money(result.ending_capital)}
              </span>
              <span className="num muted">{result.multiple}&#215;</span>
            </div>
            <div className="caption dim">from {money(result.starting_capital)}</div>
          </div>

          <div className="grid-2">
            {result.metrics.map((metric) => (
              <div key={metric.key} className="card stack" style={{ gap: "var(--gap-xs)" }}>
                <span className="row footnote muted" style={{ gap: "var(--gap-xs)" }}>
                  <span className="grow">{metric.label}</span>
                  <Tooltip label={metric.label} text={metric.help} />
                </span>
                <span className="num" style={{ fontSize: "var(--size-h3)" }}>
                  {metric.value === null ? "—" : `${metric.value}${metric.unit}`}
                </span>
                {metric.provisional && <ProvisionalBadge />}
              </div>
            ))}
          </div>

          <p className="footnote muted">{result.summary}</p>
          <p className="caption dim">
            Gross mean trade {signed(result.gross_mean_return_pct)}, net of{" "}
            {result.cost_bps_round_trip}bps round trip{" "}
            {signed(result.net_mean_return_pct)}.{" "}
            {result.benchmark.buy_and_hold_return_pct !== null && (
              <>The benchmark, held throughout, returned{" "}
              {signed(result.benchmark.buy_and_hold_return_pct)}.</>
            )}
          </p>
          {result.notes.map((note) => (
            <p key={note} className="caption dim">{note}</p>
          ))}

          <section className="stack" style={{ gap: "var(--gap-sm)" }}>
            <div className="eyebrow">Year by year</div>
            {result.yearly.map((row) => {
              const width = Math.min(100, Math.abs(row.return_pct));
              const active = yearFilter === row.year;
              return (
                <button
                  key={row.year}
                  type="button"
                  className="row"
                  aria-pressed={active}
                  style={{
                    gap: "var(--gap-sm)", background: "none", border: "none",
                    cursor: "pointer", padding: 0, width: "100%",
                  }}
                  onClick={() => {
                    setYearFilter(active ? null : row.year);
                    setTab("trades");
                  }}
                >
                  <span className="num caption" style={{ width: 38 }}>{row.year}</span>
                  <span style={{ flex: 1, height: 14, background: "var(--surface-2)",
                                 borderRadius: 2, overflow: "hidden" }}>
                    <span style={{
                      display: "block", height: "100%", width: `${width}%`,
                      background: row.return_pct >= 0 ? "var(--gain)" : "var(--loss)",
                    }} />
                  </span>
                  <span className="num caption" style={{ width: 64, textAlign: "right" }}>
                    {signed(row.return_pct)}
                  </span>
                </button>
              );
            })}
          </section>
        </div>
      )}

      {tab === "result" && !result && (
        <p className="muted footnote">Run a scan to see a result.</p>
      )}

      {tab === "trades" && (
        <div className="stack">
          {yearFilter !== null && (
            <button type="button" className="control footnote"
                    style={{ alignSelf: "flex-start" }}
                    onClick={() => setYearFilter(null)}>
              {yearFilter} only — clear
            </button>
          )}
          <div className="scroll-x card" style={{ padding: 0 }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Ticker</th><th>Entry</th><th>In</th><th>Exit</th><th>Out</th>
                  <th>Return</th><th>R</th><th>Why it ended</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade, index) => (
                  <tr key={`${trade.ticker}-${trade.entry_date}-${index}`}>
                    <td className="text mono">{trade.ticker}</td>
                    <td className="caption">{trade.entry_date}</td>
                    <td>{money(trade.entry_price, 2)}</td>
                    <td className="caption">{trade.exit_date}</td>
                    <td>{money(trade.exit_price, 2)}</td>
                    <td><PriceChange value={trade.return_pct} /></td>
                    <td>{trade.r_multiple.toFixed(2)}</td>
                    <td className="text caption dim">{trade.exit_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {trades.length === 0 && (
            <p className="muted footnote">No trades in that selection.</p>
          )}
        </div>
      )}
    </div>
  );
}
