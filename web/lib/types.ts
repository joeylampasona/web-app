export type Rating = number | string;

/** The fitted geometry behind a shape screen: two trendlines and what they
 *  imply. Every number here is measured off the fit, and several are null by
 *  design rather than by accident -- `apex_pct` is null for a flag because two
 *  parallel lines never meet, and `target` is null for a squeeze because a
 *  volatility state has no measured move to project. */
export interface ShapeGeometry {
  kind: string; start: string; end: string;
  level: number; direction: string;
  convergence: number; depth_pct: number; weeks: number;
  upper_slope_pct: number; lower_slope_pct: number;
  touches: { upper: number; lower: number };
  pole_pct: number | null; pole_sessions: number | null;
  squeeze_fired: boolean;
  /** How far through its own convergence, 0-100. Null when the lines are
   *  parallel or spreading, which is the normal answer for a flag. */
  apex_pct: number | null;
  /** Past the point where there is room left to move inside the shape. */
  stale: boolean;
  height_pct: number | null;
  target: number | null; stop: number | null;
  /** Reward over risk from the published level. Null when any leg is missing:
   *  a shape with no stop has undefined risk, not zero risk. */
  r_multiple: number | null;
  /** Squeezes only. Which way the compression has been leaning -- a reading,
   *  not a claim about the break. */
  momentum: number | null; momentum_slope: number | null;
  /** The two fitted trendlines as drawable geometry: each line's price at
   *  the ends of the shape, and the swing points it was fitted through. */
  lines?: {
    upper: ShapeLine | null;
    lower: ShapeLine | null;
  } | null;
  volume_vs_prior?: number | null; atr_vs_prior?: number | null;
  notes: string[];
}

/** One trendline, ready to draw. `touches` are the swings the least-squares
 *  fit ran through -- not all of them sit on the line. */
export interface ShapeLine {
  from: { date: string; price: number };
  to: { date: string; price: number };
  touches: { date: string; price: number }[];
}

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

/** A hand-kept FOMC date, and how much runway the list it came from has left.
 *  `stale` is the alarm: the list cannot run out without saying so. */
export interface FomcMeeting { date: string; label: string; days_until: number }

export interface FomcStatus {
  stale: boolean; runway_days: number | null; checked_on: string;
  source: string; listed: number; message: string;
  meetings: FomcMeeting[];
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
  /** Last session's volume against the prior fifty. */
  rvol?: number | null;
  /** Heavy volume, decisive close and a real gain, all in the last session. */
  ignition?: Ignition | null;
  criteria?: Criteria | null;
  /** "long" or "short" — which way the screen that found it reads its level. */
  direction?: string;
  /** Fitted geometry, on the shape screens only. */
  shape?: ShapeGeometry | null;
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
  /** "long" or "short": which way this screen reads its level. */
  direction?: string;
  /** Whether the follow-through page covers this screen. */
  has_followthrough?: boolean;
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

/** One open-market decision on the market-wide calendar.
 *
 *  Distinct from InsiderTrade below, which is the per-stock panel's row and
 *  carries the mechanics (grants, option exercises, tax withholding) alongside
 *  the decisions. This calendar only ever holds P and S. */
export interface EstimateRow {
  period: string; label: string;
  avg: number | null; low: number | null; high: number | null;
  analysts: number | null; year_ago: number | null; growth: number | null;
}

export interface Forecast {
  symbol: string;
  targets: {
    current: number | null; low: number | null;
    mean: number | null; median: number | null; high: number | null;
  };
  upside_pct: number | null;
  eps: EstimateRow[];
  revenue: EstimateRow[];
  ratings: {
    strongBuy: number; buy: number; hold: number; sell: number; strongSell: number;
  } | null;
  analysts: number | null;
  /** When we asked Yahoo, not when the analyst wrote it. */
  fetched_at?: string;
}

export interface SeasonalCell { month: number; return_pct: number | null; sessions: number }
export interface SeasonalYear {
  year: number; months: SeasonalCell[]; year_pct: number | null; partial: boolean;
}
export interface SeasonalTally {
  up: number; down: number;
  avg_pct: number | null; up_rate: number | null; observations: number;
}
export interface SeasonalSymbol {
  symbol: string; name: string; months: string[];
  years: SeasonalYear[];
  tally: Record<string, SeasonalTally>;
  observed_years: number;
}

export interface InsiderDecision {
  symbol: string; name: string; traded_at: string;
  owner: string; role: string; code: string;
  shares: number | null; price: number | null; value: number | null;
  direction: "buy" | "sell";
}

export interface InsiderDay {
  date: string;
  buys: number; sells: number;
  buy_value: number; sell_value: number;
  rows: InsiderDecision[];
}

export interface CriteriaCheck { key: string; label: string; met: boolean }

export interface Criteria {
  met: number;
  total: number;
  checks: CriteriaCheck[];
}

export interface Ignition {
  fired: boolean;
  rvol: number;
  close_in_range: number;
  gain_pct: number;
  date: string;
}

export interface VolumeRow {
  symbol: string;
  name: string;
  industry: string;
  rvol: number;
  volume: number;
  close: number;
  change_pct: number | null;
  close_in_range: number;
  market_cap: number | null;
  rs_rating: number | string | null;
}

export interface GammaBoardRow {
  symbol: string;
  name: string;
  market_cap: number | null;
  spot: number;
  open_interest: number;
  expiries: number;
  total_concentration: number;
  total_net: number;
  flip: number | null;
  stale: boolean;
  peak_strike: number;
  peak_concentration: number;
  peak_vs_spot_pct: number | null;
  levels: GammaStrike[];
}

export interface GammaStrike {
  strike: number;
  /** Unsigned dollar gamma per 1% move. Assumes nothing about positioning. */
  concentration: number;
  /** Calls positive, puts negative — the conventional signing. */
  net: number;
  call_oi: number;
  put_oi: number;
}

export interface GammaProfile {
  symbol: string;
  spot: number;
  as_of: string;
  levels: GammaStrike[];
  total_concentration: number;
  total_net: number;
  /** Where the conventional signing crosses zero. Null when it never does. */
  flip: number | null;
  contracts: number;
  open_interest: number;
  expiries: number;
  /** Open interest predates the session this page is showing. */
  stale?: boolean;
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
  gamma: GammaProfile | null;
  /** This name has gamma and it is behind the paywall. Distinct from `gamma`
   *  being null, which means there was nothing to publish — most of the
   *  universe has no listed options at all, and a page that conflated the two
   *  would advertise a subscription over companies that have nothing to sell. */
  gamma_gated?: boolean;
  forecast: Forecast | null;
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
  /** Why this stock is on none of the screens, measured against the
   *  base-and-breakout thresholds. Present only when `setups` is empty --
   *  there is nothing to explain about a stock that is on a screen. Null when
   *  it has too little history for the checks to mean anything. */
  structure_check?: StructureCheckRow[] | null;
}

/** One line of that answer. `met: null` is a third state and not a failure:
 *  the check could not be run at all, which is what "needs a base first"
 *  means. */
export interface StructureCheckRow {
  label: string; met: boolean | null; detail: string;
}

/** A broad-market index row for the home page strip. `above_200` is null when
 *  the symbol has under 200 sessions -- not enough history to have an answer. */
export interface IndexRow {
  symbol: string; name: string; close: number;
  change_pct: number | null;
  above_200: boolean | null;
  vs_200_pct: number | null;
  sessions: number;
}

/** Is the benchmark above its 200-day line? `above` is null for "cannot say",
 *  which is a third state and not the same as false. */
export interface RegimeStatus {
  symbol: string;
  above: boolean | null;
  vs_200_pct: number | null;
  sessions: number;
  note: string;
}

export interface IndexesFile {
  as_of: string; benchmark: string;
  regime: RegimeStatus;
  rows: IndexRow[];
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

/** A headline on the market-wide list, which also carries the names the
 *  article was filed against. One story usually names several. */
export interface MarketHeadline extends Headline {
  tickers: string[];
  /** "analysis" | "legal" | "release" — what sort of thing was published. */
  kind?: string;
  /** Per ticker: "setting_up", "failing", or null when it is on no screen. */
  status?: Record<string, string | null>;
  /** The article names one of the largest companies this site tracks. */
  prominent?: boolean;
}

export interface NewsFile {
  as_of: string;
  articles: MarketHeadline[];
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
