export type Rating = number | string;

export interface Contraction {
  start: string; end: string; high: number; low: number;
  depth_pct: number; weeks: number;
}

export interface BaseStructure {
  start: string; end: string; pivot: number; low: number;
  depth_pct: number; weeks: number; breakout_date: string | null;
  contractions: Contraction[];
}

export interface CatalystEvent {
  ticker: string; type: string; type_label: string; date: string;
  confirmed: string; days_until: number; title: string; details: string;
  readthrough: { from: string; tag: string; theme: string } | null;
}

/** A scheduled economic data release. Not ticker-scoped and not a forecast —
 *  the date a number comes out, nothing about what it will say. */
export interface DataRelease {
  date: string; release_id: number; name: string;
  notable: boolean; days_until: number; link: string | null;
}

export interface Setup {
  symbol: string; name: string; screen: string; stage: string;
  pivot: number; close: number;
  bases: Contraction[];
  rs_rating: Rating;
  now_vs_pivot_pct: number | null;
  tightening_atr_ratio: number | null;
  volume_dryup_ratio: number | null;
  up_down_volume_net: number | null;
  from_52w_high_pct: number | null;
  price_vs_50ma_pct: number | null;
  base_weeks: number | null;
  base_depth_pct: number | null;
  flags: string[];
  trend?: TrendAlignment | null;
  quadrant: string | null;
  breakout_date: string | null;
  sessions_since_breakout: number | null;
  breakout_metrics: {
    breakout_day_gain_pct?: number | null;
    one_day_gain_pct?: number | null;
    breakout_volume_multiple?: number | null;
    close_in_range?: number | null;
    price_vs_50ma_pct?: number | null;
    date?: string;
  };
  prior_breakout: { date: string; month: string; outcome_pct: number; reason: string } | null;
  base_history: BaseStructure[];
  catalysts: {
    next_earnings_date: string | null;
    days_until_earnings: number | null;
    earnings_within_7d: boolean;
    catalyst_roadmap: CatalystEvent[];
  };
  themes: string[];
  industry: string;
  volume: number | null;
  ohlc: {
    date: string; open: number; high: number; low: number; close: number;
    change_pct: number | null;
  };
}

export interface ScreenFile {
  screen: string; name: string; description: string; as_of: string;
  total: number;
  stage_counts: Record<string, number>;
  stage_labels: Record<string, string>;
  stage_help: Record<string, string>;
  setups: Record<string, Setup[]>;
}

export interface Meta {
  version: number; generated_at: string; as_of: string; provider: string;
  data_source: "live" | "synthetic_demo"; data_source_note?: string;
  universe_count: number; survivorship_safe: boolean; benchmark: string;
  /** Which of the Market Desk's scanners worked on the run we ingested. */
  desk_run?: DeskRun | null;
  market_wide_breakouts: number;
  screens: { key: string; name: string; total: number; stages: Record<string, number> }[];
  themes: { slug: string; name: string }[];
  disclaimer: string;
  schema_valid?: boolean;
}

export interface Bar {
  time: string; open: number; high: number; low: number; close: number; volume: number;
}

export interface StockFile {
  symbol: string; name: string; industry: string; themes: string[];
  list_date: string | null; as_of: string;
  rs_rating: Rating; rs_change_m1: number | null; market_cap: number | null;
  quadrant: string | null;
  bars: Bar[];          // expanded from compact rows by lib/data
  setups: Setup[];
  primary_setup: Setup | null;
  base_history: BaseStructure[];
  insiders: InsiderSummary | null;
  news: Headline[];
  desk_signals: DeskSignal[];
  /** The published 200-day line, aligned to `bars`. The 9, 21 and 50 are
   *  derived in the browser from those same bars.
   *
   *  Optional on purpose: a file published before moving averages existed has
   *  no such field, and that is a different fact from a stock with under a
   *  year of history, whose field is present and empty. `planMovingAverages`
   *  tells the reader which of the two applies. */
  sma200?: (number | null)[];
  catalyst_roadmap: CatalystEvent[];
  peers: { industry: { symbol: string; name: string; rs_rating: Rating }[];
           theme: { symbol: string; name: string; rs_rating: Rating }[] };
}

export interface BreadthCard {
  key: string; label: string; unit: "percent" | "count"; value: number;
  counts: Record<string, number>;
  prior_day: number | null; week_ago: number | null; wow_delta: number | null;
  series: { date: string; value: number }[];
  note: string;
}

export interface RotationPoint {
  id: string; label: string; name: string;
  x: number | null; y: number | null; quadrant: string | null;
  size: number; members?: number; leaders?: number; fresh_breakouts?: number;
}

export interface GroupRow {
  slug: string; kind: string; name: string; members: number;
  rs_rating: number | null; avg_member_rs: number; leaders: number;
  fresh_breakouts: number; market_value: number; symbols: string[];
  rs_change_w1: number | null; rs_change_m1: number | null; rs_change_m3: number | null;
  members_detail?: {
    symbol: string; name: string; rs_rating: Rating; rs_change_m1: number | null;
    market_cap: number | null; industry: string; themes: string[];
    screens: string[]; stage: string | null;
  }[];
}

export interface IVRow {
  ticker: string; name: string; event_type: string; event_label: string;
  event_date: string; confirmed: string; days_until: number;
  catalyst_expiry: string; catalyst_iv: number; neighbour_iv: number;
  iv_richness: number; iv_band: string; dots: number; week_of: string;
  neighbours: { expiry: string; iv: number }[];
}

export interface LearnFile {
  screen: string; name: string; shape: string; description: string;
  concepts: { title: string; text: string; anchor: string }[];
  funnel: { title: string; text: string; key: string }[];
  funnel_preface: string;
  funnel_callout: { text: string; cta: string; href: string };
  params: ParamSpec[];
  trade_steps: { step: number; title: string; text: string; tone: string }[];
  trade_steps_preface: string;
}

export interface ParamSpec {
  key: string; label: string; kind: string; default: unknown; value: unknown;
  minimum: number | null; maximum: number | null; step: number | null;
  unit: string; funnel_title: string; funnel_text: string; help: string;
}

export interface BacktestSummary {
  settings: Record<string, unknown>;
  hash: string;
  provisional: boolean; provisional_line: string;
  survivorship_safe: boolean;
  survivorship_line: string;
  notes: string[];
  starting_capital: number; ending_capital: number; multiple: number | null;
  years: number;
  metrics: { key: string; label: string; value: number | null; unit: string;
             help: string; provisional: boolean }[];
  summary: string;
  yearly: { year: number; return_pct: number; start_equity: number; end_equity: number }[];
  gross_mean_return_pct: number; net_mean_return_pct: number;
  cost_bps_round_trip: number;
  benchmark: { symbol: string; buy_and_hold_return_pct: number | null; help: string };
  trades: {
    ticker: string; entry_date: string; entry_price: number; exit_date: string;
    exit_price: number; shares: number; return_pct: number;
    gross_return_pct: number; r_multiple: number; exit_reason: string; pnl: number;
  }[];
}

export interface BreakoutOutcome {
  symbol: string; name: string; breakout_date: string; sessions_since: number;
  breakout_close: number; pivot: number; last_close: number;
  now_pct: number; peak_pct: number; worst_pct: number;
  failed_fast: boolean; now_below_pivot: boolean;
  rs_at_breakout: number | null;
}

export interface FollowThroughScreen {
  screen: string; name: string; window_days: number;
  total: number; settled: number; too_soon: number;
  up: number; down: number; failed_fast: number; below_pivot: number;
  median_now_pct: number | null; median_peak_pct: number | null;
  share_up_pct: number | null; share_failed_pct: number | null;
  breakouts: BreakoutOutcome[];
}

export interface FollowThroughFile {
  as_of: string | null;
  window_days: number;
  screens: Record<string, FollowThroughScreen>;
}

export interface InsiderTrade {
  traded_at: string; owner: string; role: string; code: string;
  what: string;
  /** True only for an open-market buy or sell — someone's decision. Awards,
   *  option exercises and tax withholding are mechanics, not decisions. */
  decision: boolean;
  shares: number | null; price: number | null; value: number | null;
  direction: "buy" | "sell";
}

export interface InsiderSummary {
  symbol: string; window_days: number;
  buys: number; sells: number;
  buy_value: number; sell_value: number;
  buyers: string[]; sellers: string[];
  /** Awards, exercises, gifts and tax withholding — counted, never mixed in. */
  mechanics: number;
  recent: InsiderTrade[];
}

export interface Headline {
  published_at: string; title: string; publisher: string; url: string;
}

export interface DeskSignal {
  as_of: string; source: string; reason: string; detail: string;
  magnitude: number | null; url: string;
  /** The desk believes this reading is a corporate action, not a real move. */
  suspect: boolean;
}

export interface DeskRun {
  as_of: string; generated_at: string; universe_size: number | null;
  /** Per scanner: "ok" | "failed" | "missing". An empty signal set means
   *  nothing at all if the scanner that produces it did not run. */
  stage_status: Record<string, string>;
}

export interface TrendAlignment {
  sma: Record<string, number | null>;
  /** How many of 9>21, 21>50, 50>200 hold. Three is a full stack. */
  rungs: number;
  stacked: boolean;
  price_above_all: boolean;
  /** Sessions the stack has held, or null when it is not stacked. */
  stacked_sessions: number | null;
  cooling: boolean;
}
