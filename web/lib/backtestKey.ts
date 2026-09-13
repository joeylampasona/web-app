import type { BacktestSummary } from "./types";

/** Every setting the engine accepts, allow-listed. Nothing outside these sets
 *  reaches a shell or a workflow input. Mirrors backtest/settings.py OPTIONS. */
export const ALLOWED = {
  screen: ["vcp", "blue_sky", "multi_year", "ipo", "flat_base", "cup_and_handle"],
  enter: ["breakout_close", "at_pivot"],
  exit_rule: ["trail_50d", "trail_30w", "take_25"],
  positions: [3, 5, 8, 10],
  stop_pct: [7, 8, 10],
  risk_pct: [1, 1.5, 2],
} as const;

export interface Settings {
  screen: string; enter: string; exit_rule: string;
  positions: number; stop_pct: number; risk_pct: number;
  skip_weak_markets: boolean; skip_earnings_7d: boolean;
  period: string; starting_capital: number;
}

/** Reads a request body into settings, or says which field was wrong. */
export function parseSettings(raw: Record<string, unknown>):
    { ok: true; settings: Settings } | { ok: false; error: string } {
  const s: Settings = {
    screen: String(raw.screen ?? "vcp"),
    enter: String(raw.enter ?? "breakout_close"),
    exit_rule: String(raw.exit_rule ?? "trail_50d"),
    positions: Number(raw.positions ?? 5),
    stop_pct: Number(raw.stop_pct ?? 8),
    risk_pct: Number(raw.risk_pct ?? 1.5),
    skip_weak_markets: raw.skip_weak_markets !== false,
    skip_earnings_7d: raw.skip_earnings_7d !== false,
    period: String(raw.period ?? "all"),
    starting_capital: Number(raw.starting_capital ?? 100000),
  };
  for (const [field, values] of Object.entries(ALLOWED)) {
    const value = s[field as keyof Settings];
    if (!(values as readonly unknown[]).includes(value)) {
      return { ok: false, error: `${field} must be one of ${values.join(", ")}` };
    }
  }
  if (!Number.isFinite(s.starting_capital) ||
      s.starting_capital < 1000 || s.starting_capital > 100_000_000) {
    return { ok: false, error: "starting capital must be between 1,000 and 100,000,000" };
  }
  if (s.period !== "all" && !/^\d{4}$/.test(s.period)) {
    return { ok: false, error: "period must be 'all' or a four-digit year" };
  }
  return { ok: true, settings: s };
}

/**
 * The filename a result is stored under.
 *
 * Deliberately not the Python `hash()`. Reproducing that here would mean two
 * implementations of the same key in two languages, free to drift the first
 * time either changes a separator. This key is computed once, in one place,
 * and handed to the workflow to use as a filename — Python never computes it,
 * it is just told what to call the file.
 */
export function resultKey(s: Settings): string {
  const parts = [
    s.screen, s.enter, s.exit_rule,
    `p${s.positions}`, `s${s.stop_pct}`, `r${s.risk_pct}`,
    s.skip_weak_markets ? "wk1" : "wk0",
    s.skip_earnings_7d ? "er1" : "er0",
    s.period,
    `c${Math.round(s.starting_capital)}`,
  ];
  return parts.join("-").replace(/[^a-zA-Z0-9._-]/g, "_");
}

/** Whether a precomputed preset was run with exactly these settings. */
export function sameSettings(a: Settings, b: Record<string, unknown>): boolean {
  return (
    a.screen === b.screen &&
    a.enter === b.enter &&
    a.exit_rule === b.exit_rule &&
    Number(a.positions) === Number(b.positions) &&
    Number(a.stop_pct) === Number(b.stop_pct) &&
    Number(a.risk_pct) === Number(b.risk_pct) &&
    a.skip_weak_markets === Boolean(b.skip_weak_markets) &&
    a.skip_earnings_7d === Boolean(b.skip_earnings_7d) &&
    String(a.period) === String(b.period) &&
    Number(a.starting_capital) === Number(b.starting_capital)
  );
}

export type Queued = { status: "queued"; key: string; note: string };
export type Ready = { status: "ready"; result: BacktestSummary };
export type Pending = { status: "pending"; key: string };
