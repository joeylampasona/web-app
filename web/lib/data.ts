import "server-only";
import fs from "node:fs";
import path from "node:path";
import type {
  BacktestSummary, BreadthCard, GammaBoardRow, FollowThroughFile, GroupRow, IVRow, LearnFile, Meta, RotationPoint,
  ScreenFile, StockFile,
} from "./types";

// The web layer reads static JSON the pipeline wrote. It never queries a
//
// Two locations, in order: web/out when the build fetched it there (Vercel puts
// nothing above the project root into the deployment), then the repository's
// own out/ for local development.
function resolveOut(): string {
  const candidates = [
    process.env.DATA_DIR,
    path.join(process.cwd(), "out"),
    path.resolve(process.cwd(), "..", "out"),
  ].filter(Boolean) as string[];
  for (const candidate of candidates) {
    if (fs.existsSync(path.join(candidate, "meta.json"))) return candidate;
  }
  return candidates[candidates.length - 1];
}

const OUT = resolveOut();

function read<T>(relative: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(path.join(OUT, relative), "utf-8")) as T;
  } catch {
    return null;
  }
}

function list(folder: string): string[] {
  try {
    return fs.readdirSync(path.join(OUT, folder))
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(/\.json$/, ""));
  } catch {
    return [];
  }
}

export const SCREEN_KEYS = ["vcp", "blue_sky", "multi_year", "ipo",
                            "flat_base", "cup_and_handle"] as const;
export type ScreenKey = (typeof SCREEN_KEYS)[number];

export function hasData(): boolean {
  return fs.existsSync(path.join(OUT, "meta.json"));
}

export function getMeta(): Meta | null {
  return read<Meta>("meta.json");
}

export function getScreen(key: string): ScreenFile | null {
  return read<ScreenFile>(`screens/${key}.json`);
}

export function getAllScreens(): ScreenFile[] {
  return SCREEN_KEYS.map(getScreen).filter((s): s is ScreenFile => s !== null);
}

export function getDiff() {
  return read<{
    as_of: string; first_run: boolean;
    screens: Record<string, {
      broke_out_today: string[]; newly_forming: string[];
      left: { symbol: string; from: string; to: string | null; reason: string }[];
      total: number;
    }>;
  }>("screens/diff.json");
}

export function getBreadth() {
  return read<{ as_of: string; universe_size: number; cards: BreadthCard[] }>("breadth.json");
}

export function getNews() {
  return read<import("./types").NewsFile>("news.json");
}

export function getIndexes() {
  return read<import("./types").IndexesFile>("indexes.json");
}

export function getRotation() {
  return read<{
    as_of: string; lookback_label: string;
    quadrant_labels: Record<string, string>;
    industries: { points: RotationPoint[]; counts: Record<string, number> };
    themes: { points: RotationPoint[]; counts: Record<string, number> };
    stocks: { points: RotationPoint[]; counts: Record<string, number> };
  }>("rotation.json");
}

export function getSectors() {
  return read<{
    as_of: string;
    strongest: GroupRow[]; weakest: GroupRow[];
    themes_strongest: GroupRow[]; themes_weakest: GroupRow[];
    heating_cooling: { heating: HeatRow[]; cooling: HeatRow[] };
    themes_heating_cooling: { heating: HeatRow[]; cooling: HeatRow[] };
    sector_etfs: { symbol: string; name: string; rs_rating: number | null;
                   excess_return_pct: number; close: number | null }[];
  }>("sectors.json");
}

export interface HeatRow {
  slug: string; name: string; rs_rating: number | null; avg_member_rs: number;
  delta: number; leaders: number; fresh_breakouts: number; members: number;
}

export function getTreemap() {
  return read<{
    as_of: string; windows: string[];
    tiles: {
      slug: string; name: string; market_value: number; weight: number;
      rs_rating: number | null; rs_change_w1: number | null;
      rs_change_m1: number | null; rs_change_m3: number | null;
      fresh_breakouts: number; members: number; leaders: number;
    }[];
  }>("treemap.json");
}

export function getUpcoming() {
  return read<{
    as_of: string; count: number; owned: number; readthrough: number;
    events: import("./types").CatalystEvent[];
    type_labels: Record<string, string>;
  }>("catalysts/upcoming.json");
}

export function getReleases() {
  return read<{
    as_of: string; configured: boolean; count: number; source: string;
    releases: import("./types").DataRelease[];
    fomc?: import("./types").FomcStatus;
  }>("catalysts/releases.json");
}

export function getHighIV() {
  return read<{
    as_of: string;
    copy: { header: string; subhead: string; footer: string };
    band_labels: Record<string, string>;
    dots: number;
    rows: IVRow[];
  }>("catalysts/high_iv.json");
}

export function getLearn(key: string): LearnFile | null {
  return read<LearnFile>(`learn/${key}.json`);
}

export function getAllLearn(): LearnFile[] {
  return SCREEN_KEYS.map(getLearn).filter((l): l is LearnFile => l !== null);
}

/** The pipeline writes bars as rows to keep the tree small. Expand at this
 *  boundary so every component keeps seeing plain objects. */
function expandBars(raw: unknown): import("./types").Bar[] {
  if (!Array.isArray(raw)) return [];
  return (raw as unknown[]).map((row) => {
    if (Array.isArray(row)) {
      const [time, open, high, low, close, volume] = row as [
        string, number, number, number, number, number,
      ];
      return { time, open, high, low, close, volume };
    }
    return row as import("./types").Bar;
  });
}

export function getStock(symbol: string): StockFile | null {
  const file = read<StockFile>(`stocks/${symbol.toUpperCase()}.json`);
  if (!file) return null;
  return { ...file, bars: expandBars(file.bars as unknown) };
}

export function listStocks(): string[] {
  return list("stocks");
}

export function getGroup(kind: "industries" | "themes", slug: string): GroupRow | null {
  return read<GroupRow>(`${kind}/${slug}.json`);
}

export function listGroups(kind: "industries" | "themes"): string[] {
  return list(kind);
}

export function getBreakoutDates(): string[] {
  return read<{ dates: string[] }>("breakouts/index.json")?.dates ?? [];
}

export function getBreakouts(date: string) {
  return read<{
    date: string; count: number; metric_set: string[];
    setups: import("./types").Setup[];
  }>(`breakouts/${date}.json`);
}

export function getBacktestOptions() {
  return read<{
    options: Record<string, {
      label: string; control: string;
      options?: { value: string | number | boolean; label: string }[];
      min?: number; max?: number; step?: number;
    }>;
    defaults: Record<string, unknown>;
    years: number[];
  }>("backtest/options.json");
}

export function getBacktestPresetIndex() {
  return read<{
    default_by_screen: Record<string, string>;
    /** The session these were computed against. */
    as_of?: string | null;
    /** Hash to the exact settings it was run with, so a request can be matched
     *  against what is already computed without recomputing the hash here. */
    presets?: Record<string, Record<string, unknown>>;
  }>("backtest/presets/index.json");
}

export function getBacktestPreset(hash: string): BacktestSummary | null {
  return read<BacktestSummary>(`backtest/presets/${hash}.json`);
}

export function getDefaultBacktest(screen: string): BacktestSummary | null {
  const index = getBacktestPresetIndex();
  const hash = index?.default_by_screen?.[screen];
  return hash ? getBacktestPreset(hash) : null;
}

export function getGammaBoard() {
  return read<{
    as_of: string;
    count: number;
    rows: GammaBoardRow[];
    copy: { header: string; subhead: string; footer: string };
  }>("market/gamma.json");
}

export function getFollowThrough() {
  return read<FollowThroughFile>("breakouts/followthrough.json");
}

/** A small index for search: every universe name with its RS and industry. */
export interface SearchRow {
  symbol: string; name: string; industry: string; rs_rating: number | string;
  themes: string[];
  /** Normalised 0-100 price shape for rows that have no room for a chart.
   *  Null when the window was too short or dead flat -- a flat line and a
   *  missing one look the same to a reader and only one is true. */
  spark?: number[] | null;
  spark_change_pct?: number | null;
}

export function getSearchIndex(): SearchRow[] {
  // One file, written by the pipeline. This used to open every stock file on
  // the first keystroke and hold the lot in memory for the life of the process.
  const file = read<{ rows: SearchRow[] }>("search.json");
  if (file?.rows?.length) return file.rows;

  // An out/ tree published before search.json existed. Rebuild from the stock
  // files rather than returning nothing and letting the page tell the reader
  // their ticker is not in the universe, which would be a lie.
  const rows: SearchRow[] = [];
  for (const symbol of listStocks()) {
    const stock = getStock(symbol);
    if (!stock) continue;
    rows.push({
      symbol: stock.symbol, name: stock.name, industry: stock.industry,
      rs_rating: stock.rs_rating, themes: stock.themes,
    });
  }
  rows.sort((a, b) => a.symbol.localeCompare(b.symbol));
  return rows;
}

/** Trimmed bars for a set of symbols, for the charts on a card list. */
/**
 * How many cards get their chart with the page itself. Enough to fill the first
 * screenful on a phone with no flash; everything below fetches its own as it
 * scrolls into view. Sending all of them made one screen a 5MB download.
 */
export const EAGER_CHARTS = 6;

export function barsFor(symbols: string[], limit = 90): Record<string, import("./types").Bar[]> {
  const out: Record<string, import("./types").Bar[]> = {};
  for (const symbol of symbols) {
    const stock = getStock(symbol);
    if (stock?.bars?.length) out[symbol] = stock.bars.slice(-limit);
  }
  return out;
}
