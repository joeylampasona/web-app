import "server-only";
import {
  getDealerGamma, getBreadth, getEarnings, getEdition, getEditions, getIndexes,
  getMarketContext, getMeta, getRadar, getScreen, getSearchIndex, getStock,
} from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";
import { readReporters } from "./note";
import { failed, type Server, type Tool, type ToolResult } from "./protocol";

/**
 * What a reader's own AI may ask The Tape.
 *
 * Every tool here reads the published tree through the same loaders the
 * public pages use, and returns what a signed-out visitor to the site would
 * see on the page of the same name. That is the whole security model, so it
 * is worth saying what it rests on: the published tree never held the paid
 * half. A screen's file carries its free sample and the true counts; the
 * full lists live in a database this code does not open. Nothing here widens
 * what is public, and nothing here could.
 *
 * The answers are written for a model to read, which means small. A stock's
 * page is two megabytes of bars and averages; its answer here is a
 * screenful. Each answer says what day it is for, what its numbers are
 * measured in, and the caveats the page itself carries.
 */

const SITE = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://thetape.cc").replace(/\/$/, "");

/** The most text one answer may carry. A model's context is the reader. */
const MAX_CHARS = 14_000;

const SYMBOL = "^[A-Za-z][A-Za-z.\\-]{0,7}$";
const DAY = "^\\d{4}-\\d{2}-\\d{2}$";

type Loose = Record<string, unknown>;

function obj(value: unknown): Loose {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Loose) : {};
}

function arr(value: unknown): Loose[] {
  return Array.isArray(value) ? (value as Loose[]) : [];
}

/** A number to a sensible few places; anything else untouched. */
function n(value: unknown, places = 2): unknown {
  if (typeof value !== "number" || !Number.isFinite(value)) return value ?? null;
  const scale = 10 ** places;
  return Math.round(value * scale) / scale;
}

function pick(source: unknown, keys: string[], places = 2): Loose {
  const from = obj(source);
  const out: Loose = {};
  for (const key of keys) {
    if (from[key] !== undefined && from[key] !== null) out[key] = n(from[key], places);
  }
  return out;
}

function clip(text: unknown, limit: number): string {
  const line = String(text ?? "");
  return line.length > limit ? `${line.slice(0, limit - 1).trimEnd()}…` : line;
}

/** One top-level key a line, each value compact. Valid JSON, a third the
 *  size of an indented dump, and a person can still find their place in it. */
function render(payload: Loose): string {
  const lines = Object.entries(payload)
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) => `${JSON.stringify(key)}: ${JSON.stringify(value)}`);
  return `{\n${lines.join(",\n")}\n}`;
}

/** An answer. One too long to send is not cut off part-way, which would hand
 *  the model broken JSON to guess at: it is replaced by a short answer saying
 *  how to ask for less. */
function say(payload: Loose, askForLess = "Ask a narrower question."): ToolResult {
  const text = render(payload);
  if (text.length <= MAX_CHARS) return { content: [{ type: "text", text }] };
  return {
    content: [{ type: "text", text: render({
      as_of: payload.as_of, notes: payload.notes,
      too_long: `This answer came to ${text.length.toLocaleString()} characters, over the `
                + `${MAX_CHARS.toLocaleString()} this connection sends at once. ${askForLess}`,
      page: payload.page,
    }) }],
  };
}

/** The caveats every answer carries, in the site's own words. */
function standing(): Loose {
  const meta = getMeta();
  const notes = [
    "End-of-day data from the last completed session, not live prices.",
    "A stock on a screen matches a shape. That is a description, not a prediction, and nothing here is investment advice.",
  ];
  if (meta?.data_source === "synthetic_demo") {
    notes.unshift("DEMO DATA: this build is a fixture. Tickers, names and prices are invented.");
  }
  return { as_of: meta?.as_of ?? null, notes };
}

function noTree(): ToolResult {
  return failed("The Tape has no published edition to read at the moment.");
}

// ---------------------------------------------------------------- edition

const getEditionTool: Tool = {
  name: "get_edition",
  title: "The day's edition",
  description:
    "The Tape's nightly edition for one session: the one-word read of the market and the "
    + "sentence behind it, the checks it rests on, breadth, which groups lead, how many names "
    + "are on each screen, and the source report (which data sources answered that night and "
    + "which are stale). Call this first to learn what day the data is for. Without a date it "
    + "returns the newest edition.",
  inputSchema: {
    type: "object",
    properties: {
      date: { type: "string", pattern: DAY, maxLength: 10,
              description: "A session date as YYYY-MM-DD. Omit for the newest edition." },
    },
    additionalProperties: false,
  },
  run(args) {
    const meta = getMeta();
    if (!meta) return noTree();
    const wanted = typeof args.date === "string" ? args.date : meta.as_of;
    const edition = getEdition(wanted);
    if (!edition) {
      const dates = (getEditions()?.editions ?? []).slice(0, 12).map((e) => e.date);
      return failed(`No edition for ${wanted}. Recent editions: ${dates.join(", ") || "none"}.`);
    }
    const newest = wanted === meta.as_of;
    return say({
      ...standing(),
      edition: edition.date,
      read: edition.headline,
      why: edition.blurb,
      checks: edition.checks,
      indexes: arr(edition.indexes).map((r) => pick(r, ["symbol", "close", "vs_200_pct", "above_200"])),
      breadth: edition.breadth.map((b) => ({ label: b.label, value: n(b.value, 1), unit: b.unit })),
      leadership: edition.radar
        ? { label: edition.radar.label, detail: edition.radar.sub,
            leading: edition.radar.leaders, weakest: edition.radar.weakest }
        : null,
      screens: arr(edition.screens).map((s) => ({ key: s.key, name: s.name, names_on_it: s.total })),
      universe: edition.universe ?? meta.universe_count,
      older_edition: edition.older,
      // Only the newest edition has a source report: it describes the run
      // that built the tree being read.
      sources: newest
        ? arr(meta.sources).map((s) => ({ source: s.label, from: s.from, status: s.status,
                                          detail: s.detail, covers: s.as_of }))
        : undefined,
      generated_at: newest ? meta.generated_at : undefined,
      page: `${SITE}/`,
    });
  },
};

// ---------------------------------------------------------------- screens

function setupRow(row: Loose): Loose {
  const out = pick(row, ["symbol", "name", "stage", "pivot", "close", "now_vs_pivot_pct", "rs_rating",
                         "base_weeks", "base_depth_pct", "breakout_date", "sessions_since_breakout",
                         "rvol", "industry", "sp500", "nights"]);
  const flags = Array.isArray(row.flags) ? row.flags : [];
  if (flags.length) out.flags = flags;
  const next = obj(row.catalysts).next_earnings_date;
  if (next) out.next_earnings = next;
  const criteria = obj(row.criteria);
  if (criteria.total) out.criteria_met = `${criteria.met} of ${criteria.total}`;
  return out;
}

const listScreensTool: Tool = {
  name: "list_screens",
  title: "The screens",
  description:
    "Every screen The Tape runs, with its key, what shape it looks for, which way it reads "
    + "(long or short), and how many names are on it at each stage tonight. Use the key with "
    + "get_screen. Counts are the true totals; get_screen returns only the public sample.",
  inputSchema: { type: "object", properties: {}, additionalProperties: false },
  run() {
    const meta = getMeta();
    if (!meta) return noTree();
    return say({
      ...standing(),
      screens: meta.screens.map((s) => {
        const file = getScreen(s.key);
        return {
          key: s.key, name: s.name, direction: file?.direction ?? "long",
          looks_for: clip(file?.description, 260),
          names_on_it: s.total, by_stage: s.stages,
          page: `${SITE}/screens/${s.key}`,
        };
      }),
    });
  },
};

const getScreenTool: Tool = {
  name: "get_screen",
  title: "One screen",
  description:
    "One screen's public sample: the names a signed-out visitor sees on its page, each with "
    + "its stage, pivot (the price it would have to clear), last close, distance from the "
    + "pivot in percent, relative-strength rating (1-99), base length and depth, and breakout "
    + "date where it has broken out. Also the true count at every stage, so you can say how "
    + "much is withheld. The full lists are for subscribers on the site and are not available "
    + "here. Get the key from list_screens.",
  inputSchema: {
    type: "object",
    properties: {
      screen: { type: "string", pattern: "^[a-z][a-z0-9_]{1,39}$", maxLength: 40,
                description: "A screen key from list_screens, for example vcp or blue_sky." },
      stage: { type: "string", pattern: "^[a-z][a-z0-9_]{1,39}$", maxLength: 40,
               description: "Only this stage, for example forming or fresh_breakout. Omit for all." },
    },
    required: ["screen"],
    additionalProperties: false,
  },
  run(args) {
    const meta = getMeta();
    if (!meta) return noTree();
    const keys = meta.screens.map((s) => s.key);
    const key = String(args.screen);
    // Checked against the list, not just the pattern: the key becomes part
    // of a file name.
    if (!keys.includes(key)) return failed(`No screen "${key}". The screens are: ${keys.join(", ")}.`);
    const file = getScreen(key);
    if (!file) return failed(`The screen "${key}" has no published file tonight.`);
    const stages = Object.keys(file.stage_counts);
    const only = typeof args.stage === "string" ? args.stage : null;
    if (only && !stages.includes(only)) {
      return failed(`"${key}" has no stage "${only}". Its stages are: ${stages.join(", ")}.`);
    }
    const locked = new Set(file.locked_stages ?? []);
    let shown = 0;
    const byStage = stages.filter((s) => !only || s === only).map((stage) => {
      const rows = arr(file.setups[stage]).map(setupRow);
      shown += rows.length;
      return {
        stage, label: file.stage_labels[stage], meaning: file.stage_help[stage],
        names_at_this_stage: file.stage_counts[stage],
        shown_here: rows.length,
        withheld: locked.has(stage)
          ? "This stage is for subscribers; none of it is shown publicly."
          : (file.stage_counts[stage] > rows.length ? "The rest are for subscribers." : undefined),
        rows,
      };
    });
    return say({
      ...standing(),
      screen: file.screen, name: file.name, direction: file.direction ?? "long",
      looks_for: file.description,
      names_on_it: file.total, shown_here: shown,
      public_sample: file.gated
        ? `A public sample. ${SITE_NAME} shows subscribers the full lists on the site; they are not available through this connection.`
        : undefined,
      units: "pivot and close in dollars; now_vs_pivot_pct, base_depth_pct in percent; base_weeks in weeks; rvol is volume against its own average; rs_rating is a 1-99 rank.",
      stages: byStage,
      page: `${SITE}/screens/${file.screen}`,
    }, `Ask for one stage at a time with the "stage" argument: ${stages.join(", ")}.`);
  },
};

// ------------------------------------------------------------------ stock

const getStockTool: Tool = {
  name: "get_stock",
  title: "One company",
  description:
    "The Tape's public page for one US-listed company, trimmed: what it is, its "
    + "relative-strength rating, the setup it is in (stage, pivot, base) or why it is on no "
    + "screen, support and resistance, its coming dated events, the move options price into "
    + "its next report with the night that was read, the read of its last filed quarter, "
    + "short interest and short volume, the options read, trades by members of the House, "
    + "and signals from the overnight market sweep. Figures behind the paywall are named as "
    + "withheld, not shown. Daily bars are left out unless you ask for them.",
  inputSchema: {
    type: "object",
    properties: {
      symbol: { type: "string", pattern: SYMBOL, maxLength: 8,
                description: "A ticker, for example NVDA or BRK.B. Use search_stocks to find one." },
      bars: { type: "integer", minimum: 0, maximum: 60,
              description: "How many of the latest daily bars to include, 0 to 60. Default 0." },
    },
    required: ["symbol"],
    additionalProperties: false,
  },
  run(args) {
    if (!getMeta()) return noTree();
    const symbol = String(args.symbol).toUpperCase();
    const stock = getStock(symbol);
    if (!stock) {
      return failed(`${symbol} is not in The Tape's universe (liquid US-listed companies). `
                    + "Use search_stocks to look for it by name.");
    }
    const loose = stock as unknown as Loose;
    const last = stock.bars[stock.bars.length - 1];
    const prev = stock.bars[stock.bars.length - 2];

    const setup = obj(loose.primary_setup);
    const others = arr(loose.setups).map((s) => s.screen).filter((s) => s !== setup.screen);

    const priced = obj(loose.earnings_priced);
    const fundamentals = obj(loose.fundamentals);
    const quarter = obj(fundamentals.quarterly);
    const options = obj(loose.options_read);

    const withheld: string[] = [];
    if (loose.gamma_gated) withheld.push("gamma by strike");
    if (loose.forecast_gated) withheld.push("analyst forecasts");
    if (loose.holders_gated) withheld.push("which tracked funds hold it");
    if (loose.earnings_moves_gated) withheld.push("its dated earnings moves");
    if (loose.xray_gated) withheld.push("its full base history");

    const wantBars = typeof args.bars === "number" ? args.bars : 0;

    return say({
      ...standing(),
      symbol: stock.symbol, name: stock.name, industry: stock.industry, themes: stock.themes,
      market_cap: n(loose.market_cap, 0), in_sp500: loose.sp500 ?? undefined,
      rs_rating: stock.rs_rating, rs_change_1m: n(loose.rs_change_m1, 0),
      last_session: last
        ? { date: last.time, close: n(last.close), volume: last.volume,
            change_pct: prev ? n(100 * (last.close / prev.close - 1)) : null }
        : null,
      range_52w: pick(loose.range_52w, ["low", "high"]),
      setup: setup.screen
        ? { ...setupRow(setup), screen: setup.screen,
            also_on: others.length ? others : undefined }
        : null,
      why_on_no_screen: setup.screen
        ? undefined
        : arr(loose.structure_check).map((c) => ({ check: c.label, met: c.met, detail: c.detail })),
      levels: {
        ...pick(loose.levels, ["atr"]),
        support: pick(obj(loose.levels).support, ["price", "touches"]),
        resistance: pick(obj(loose.levels).resistance, ["price", "touches"]),
        note: "Prices tested three or more times in the last 120 sessions. Where they sit, not a forecast. atr is the average daily range in dollars.",
      },
      against_its_industry: pick(loose.leadership, ["label", "vs", "rs21", "rs63", "rs126"]),
      coming: arr(loose.catalyst_roadmap).slice(0, 5).map((e) => ({
        ...pick(e, ["date", "type_label", "confirmed", "days_until", "priced_move_pct", "priced_read_on"]),
        title: clip(e.title, 90),
        priced_move_is_stale: e.priced_stale ? true : undefined,
      })),
      options_price_into_next_report: priced.implied_pct
        ? { ...pick(priced, ["report_date", "hour", "expiry", "implied_pct"]),
            read_on: priced.d ?? null, stale: Boolean(priced.stale),
            note: "The at-the-money straddle as a percent of price, either way. From the Market Desk; an options reading, not a call on the stock." }
        : null,
      last_priced_move: pick(loose.earnings_priced_last, ["report_date", "implied_pct", "realised_pct", "inside"]),
      last_filed_quarter: quarter.takeaway
        ? { takeaway: quarter.takeaway, verdict: quarter.verdict,
            report_date: quarter.report_date ?? null,
            covers_reported_quarter: quarter.covers ?? null,
            quarter_ended: obj(quarter.glance).end ?? null,
            points: arr(quarter.flags).slice(0, 5).map((f) => f.text),
            note: "Built by fixed rules from the company's 10-Q figures." }
        : null,
      fundamentals_ttm: pick(fundamentals, ["period_end", "revenue_ttm", "revenue_growth", "gross_margin",
                                            "op_margin", "net_margin", "fcf_ttm", "price_to_sales",
                                            "price_to_earnings"], 3),
      short_interest: loose.short_interest
        ? { ...pick(loose.short_interest, ["settlement", "shares", "chg_pct", "days_to_cover"]),
            note: "FINRA, published twice a month. Present only for names the Market Desk flagged." }
        : null,
      short_volume: loose.short_volume
        ? { ...pick(loose.short_volume, ["ratio", "ratio_20d", "sessions", "d"], 3),
            note: "Share of the session's volume marked short (0.44 = 44%), against its 20-session mean. Market makers hedging count, so about half is ordinary." }
        : null,
      options_read: options.d
        ? { ...pick(options, ["iv30", "iv_rank", "exp_move_pct", "exp_move_expiry", "pc_oi", "pc_vol",
                              "call_wall", "put_wall", "max_pain"]),
            read_on: options.d, stale: Boolean(options.stale),
            note: "From the Market Desk. iv30 and exp_move_pct in percent; iv_rank is null until 20 reads exist." }
        : null,
      tracked_funds_holding: pick(loose.holders, ["n", "new", "added", "trimmed", "sold", "period"]),
      house_members_trades: Array.isArray(loose.congress)
        ? arr(loose.congress).slice(0, 6).map((t) => pick(t, ["member", "district", "type", "owner", "traded",
                                                              "filed", "amount_low", "amount_high"], 0))
        : undefined,
      insiders: loose.insiders
        ? pick(loose.insiders, ["window_days", "buys", "sells", "buy_value", "sell_value"], 0)
        : null,
      overnight_brief_line: obj(loose.desk_story).text
        ? { text: clip(obj(loose.desk_story).text, 280), read_on: obj(loose.desk_story).d ?? null,
            stale: Boolean(obj(loose.desk_story).stale),
            note: "The one sentence the Market Desk's brief led this name with. Absent when its brief did not rank the name." }
        : null,
      overnight_sweep_signals: arr(loose.desk_signals).slice(0, 6).map((s) => ({
        ...pick(s, ["as_of", "source", "reason"]),
        detail: clip(s.detail, 120),
        track_record: obj(s.track).read || undefined,
      })),
      headlines: arr(loose.news).slice(0, 4).map((h) => ({
        when: String(h.published_at ?? "").slice(0, 10), title: clip(h.title, 140), publisher: h.publisher,
      })),
      for_subscribers_on_the_site: withheld.length ? withheld : undefined,
      bars: wantBars > 0
        ? { format: ["date", "open", "high", "low", "close", "volume"],
            rows: stock.bars.slice(-wantBars).map((b) => [b.time, b.open, b.high, b.low, b.close, b.volume]) }
        : undefined,
      page: `${SITE}/stocks/${stock.symbol}`,
    }, "Ask again with fewer bars.");
  },
};

// --------------------------------------------------------------- earnings

const getEarningsTool: Tool = {
  name: "get_earnings",
  title: "Earnings",
  description:
    "Who has just reported and how the price took it (read twice a day, about 9:20am and "
    + "6:00pm New York, so newer than the rest of the data), how earlier reactions held up "
    + "over a full session, the move options price into the coming reports with the night "
    + "each was read, how often priced moves have held, and the newest reads of filed "
    + "quarters. Moves are percent; reaction prices are delayed quotes read once.",
  inputSchema: { type: "object", properties: {}, additionalProperties: false },
  async run() {
    if (!getMeta()) return noTree();
    const file = getEarnings();
    const note = await readReporters();
    const priced = obj(file?.priced);
    return say({
      ...standing(),
      reported: {
        day: note.date,
        is_today_in_new_york: note.date !== null && note.date === note.today,
        note: "Delayed quotes read once at read_at (New York time): before and after the bell they are quotes in thin trading, not the session's move. Figures against estimates are as first published. The companies named are the largest and most followed of the day's reporters, not all of them.",
        rows: note.rows.map((r) => pick(r, ["symbol", "name", "move", "when", "implied", "eps", "estimate",
                                            "surprise_pct", "revenue", "revenue_estimate",
                                            "revenue_surprise_pct", "read_at"])),
      },
      settled: {
        note: "A report before the bell settles in that day's session, one after it in the next day's, close to close. inside means the session move was no larger than options had priced.",
        rows: note.settled.slice(0, 15).map((r) => pick(r, ["symbol", "name", "reported", "when", "first_move",
                                                            "session_move", "settled_on", "implied", "inside"])),
      },
      priced_into_coming_reports: {
        note: "implied_pct is the at-the-money straddle at the first expiry after the report, as a percent of price. d is the night it was read; stale means that read is older than it should be. From the Market Desk.",
        rows: arr(priced.upcoming).slice(0, 25).map((r) => pick(r, ["ticker", "report_date", "hour", "implied_pct",
                                                                    "hist_avg_pct", "ratio", "d", "stale"])),
        record: pick(priced.tally, ["n", "inside_pct", "mean_ratio"]),
      },
      reads_of_filed_quarters: arr(file?.reads).slice(0, 6).map((r) => ({
        symbol: r.symbol, name: r.name, report_date: r.report_date,
        takeaway: r.takeaway, verdict: r.verdict,
      })),
      page: `${SITE}/market/earnings`,
    });
  },
};

// ---------------------------------------------------------------- context

/** context.json keys this file names itself; anything else the pipeline adds
 *  later is passed through as it stands, so a new reading shows up here the
 *  night it is published. */
const CONTEXT_KNOWN = new Set(["as_of", "put_call", "regime", "earnings_priced", "events_crossing", "source"]);

const getMarketContextTool: Tool = {
  name: "get_market_context",
  title: "The market's state",
  description:
    "The state of the US market behind the screens: the indexes against their 200-day "
    + "averages, breadth (how much of the universe is above its averages, at highs, breaking "
    + "out) against a day and a week ago, which groups lead, put/call ratios, the Market "
    + "Desk's regime label, scheduled macro releases in the next five sessions, and dealer "
    + "gamma for the index and sector funds with the night it was read.",
  inputSchema: { type: "object", properties: {}, additionalProperties: false },
  run() {
    if (!getMeta()) return noTree();
    const indexes = getIndexes();
    const context = obj(getMarketContext());
    const radar = obj(getRadar());
    const gamma = getDealerGamma();
    const extra: Loose = {};
    for (const [key, value] of Object.entries(context)) {
      if (!CONTEXT_KNOWN.has(key) && value !== null) extra[key] = value;
    }
    return say({
      ...standing(),
      indexes: {
        note: indexes?.regime?.note ?? null,
        rows: arr(indexes?.rows).map((r) => pick(r, ["symbol", "name", "close", "change_pct", "vs_50_pct",
                                                     "vs_200_pct", "above_200", "from_high_pct"])),
      },
      breadth: arr(getBreadth()?.cards).map((c) => ({
        ...pick(c, ["label", "value", "unit", "prior_day", "week_ago"], 1),
        note: clip(c.note, 140) || undefined,
      })),
      leadership: radar.label ? { label: radar.label, detail: radar.sub } : null,
      put_call: context.put_call ?? null,
      regime: context.regime ?? null,
      macro_releases_next_five_sessions: arr(context.events_crossing),
      ...extra,
      dealer_gamma: gamma
        ? { read_on: gamma.read_on, stale: gamma.stale,
            note: "The Market Desk's reading on the usual convention that dealers are long calls and short puts, which is an assumption and is not in the data. net is dollars per 1% move.",
            index: gamma.index.map((r) => pick(r, ["symbol", "label", "spot", "net", "regime", "flip",
                                                   "flip_pct", "call_wall", "put_wall"])),
            sectors: gamma.sectors.map((r) => pick(r, ["symbol", "label", "net", "regime"])) }
        : null,
      pages: [`${SITE}/market/breadth`, `${SITE}/market/gamma`],
    });
  },
};

// ----------------------------------------------------------------- search

const searchStocksTool: Tool = {
  name: "search_stocks",
  title: "Find a company",
  description:
    "Find companies in The Tape's universe by ticker, name or industry. Returns the best "
    + "matches with ticker, name, industry, relative-strength rating (1-99), last close and "
    + "that session's change in percent. Use the ticker with get_stock.",
  inputSchema: {
    type: "object",
    properties: {
      query: { type: "string", maxLength: 40,
               description: "A ticker, part of a company name, or an industry." },
      limit: { type: "integer", minimum: 1, maximum: 25, description: "How many to return. Default 10." },
    },
    required: ["query"],
    additionalProperties: false,
  },
  run(args) {
    if (!getMeta()) return noTree();
    const needle = String(args.query).trim().toLowerCase();
    if (!needle) return failed("Give a ticker, part of a name, or an industry to search for.");
    const limit = typeof args.limit === "number" ? args.limit : 10;
    // Ranked the way the site's own search is: the exact ticker, tickers
    // that start with it, names that start with it, names that contain it,
    // then industries.
    const scored: { score: number; row: ReturnType<typeof getSearchIndex>[number] }[] = [];
    for (const row of getSearchIndex()) {
      const symbol = row.symbol.toLowerCase();
      const name = row.name.toLowerCase();
      const score = symbol === needle ? 0
        : symbol.startsWith(needle) ? 1
        : name.startsWith(needle) ? 2
        : name.includes(needle) ? 3
        : row.industry.toLowerCase().includes(needle) ? 4 : -1;
      if (score >= 0) scored.push({ score, row });
    }
    const rs = (v: number | string) => (typeof v === "number" ? v : -1);
    scored.sort((a, b) => a.score - b.score || rs(b.row.rs_rating) - rs(a.row.rs_rating));
    return say({
      ...standing(),
      query: needle, matches: scored.length,
      rows: scored.slice(0, limit).map(({ row }) => ({
        symbol: row.symbol, name: row.name, industry: row.industry, rs_rating: row.rs_rating,
        close: n(row.close), change_pct: n(row.change_pct),
      })),
    });
  },
};

export const SERVER: Server = {
  name: "the-tape",
  title: SITE_NAME,
  version: "1.0.0",
  instructions:
    `${SITE_NAME} is an end-of-day screening and market-analytics site for US stocks: it finds `
    + "companies whose price is forming or leaving a base, and publishes what the market did "
    + "around them. These tools read its public pages. Start with get_edition to learn what "
    + "session the data is for. Everything is from the last completed session unless a tool "
    + "says otherwise; nothing is a live price. Screens return a public sample and the true "
    + "counts; the full lists are for subscribers on the site. A stock on a screen matches a "
    + "shape, which is a description and not a prediction. Nothing here is investment advice, "
    + "and you should say so when a reader asks what to buy.",
  tools: [getEditionTool, listScreensTool, getScreenTool, getStockTool, getEarningsTool,
          getMarketContextTool, searchStocksTool],
};
