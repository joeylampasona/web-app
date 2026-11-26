/**
 * The earnings reactions the reporters job posts, as a public page may show
 * them.
 *
 * The job runs twice a day, about 9:20 and 6:00 in New York, and keeps a
 * note on the repository's `reporters` branch. The note holds more than this:
 * which companies it has already named, which filings it has read, which
 * reactions are still waiting on a session. None of that is for a reader.
 * What is here is what was reported and how the price took it, which are
 * public facts about public companies. Which screen a name is on is not in
 * the note's public rows at all, and nothing here joins them back to one.
 */

/** One reaction line: who reported, and where the price was when it was read. */
export interface ReportedRow {
  symbol: string;
  name: string | null;
  /** Percent, from a delayed quote. Null when there was no quote to read. */
  move: number | null;
  when: string | null;
  /** What the options had priced, percent either way. */
  implied: number | null;
  eps: number | null;
  estimate: number | null;
  surprise_pct: number | null;
  revenue: number | null;
  revenue_estimate: number | null;
  revenue_surprise_pct: number | null;
  day: string | null;
  run: string | null;
  /** New York local time the prices were read, no offset. */
  read_at: string | null;
  /** Whether the site has a page for the company. Added by the route. */
  has_page: boolean;
}

/** A reaction after a full regular session. */
export interface SettledRow {
  symbol: string;
  name: string | null;
  reported: string | null;
  when: string | null;
  first_move: number | null;
  session_move: number | null;
  settled_on: string | null;
  implied: number | null;
  inside: boolean | null;
  has_page: boolean;
}

export interface ReportersPayload {
  /** The New York day the rows are from. */
  date: string | null;
  /** Today in New York when the route answered, so "today" means the same
   *  thing on the server and in a browser in another time zone. */
  today: string;
  rows: ReportedRow[];
  settled: SettledRow[];
}

const NEW_YORK_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
});

export function newYorkToday(now: Date = new Date()): string {
  return NEW_YORK_DAY.format(now);
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

function isoDay(value: unknown): string | null {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : null;
}

/** How many days of settled reactions the page keeps. The note keeps forty
 *  rows however old; a reaction from three weeks ago is not news. */
export const SETTLED_DAYS = 10;
/** Past this many days the reaction lines are an old note, not a late one. */
export const ROWS_DAYS = 6;

function daysBetween(earlier: string, later: string): number {
  return Math.round((Date.parse(`${later}T12:00:00Z`) - Date.parse(`${earlier}T12:00:00Z`))
    / 86_400_000);
}

/**
 * The note, cut down to what a reader may have.
 *
 * Field by field rather than by spreading the row, so a field added to the
 * note later does not reach a browser because nobody remembered this file.
 */
export function publicReporters(
  note: unknown,
  hasPage: (symbol: string) => boolean,
  today: string = newYorkToday(),
): ReportersPayload {
  const empty: ReportersPayload = { date: null, today, rows: [], settled: [] };
  if (!note || typeof note !== "object") return empty;
  const raw = note as Record<string, unknown>;
  const date = isoDay(raw.date);

  const rows: ReportedRow[] = [];
  const fresh = date !== null && daysBetween(date, today) <= ROWS_DAYS
    && daysBetween(date, today) >= 0;
  for (const item of Array.isArray(raw.rows) && fresh ? raw.rows : []) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const symbol = text(row.symbol)?.toUpperCase();
    if (!symbol) continue;
    rows.push({
      symbol, name: text(row.name),
      move: num(row.move), when: text(row.when), implied: num(row.implied),
      eps: num(row.eps), estimate: num(row.estimate), surprise_pct: num(row.surprise_pct),
      revenue: num(row.revenue), revenue_estimate: num(row.revenue_estimate),
      revenue_surprise_pct: num(row.revenue_surprise_pct),
      day: isoDay(row.day), run: text(row.run), read_at: text(row.read_at),
      has_page: hasPage(symbol),
    });
  }

  const settled: SettledRow[] = [];
  for (const item of Array.isArray(raw.settled) ? raw.settled : []) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const symbol = text(row.symbol)?.toUpperCase();
    const on = isoDay(row.settled_on);
    if (!symbol || num(row.session_move) === null) continue;
    if (on && (daysBetween(on, today) > SETTLED_DAYS || daysBetween(on, today) < 0)) continue;
    settled.push({
      symbol, name: text(row.name), reported: isoDay(row.reported), when: text(row.when),
      first_move: num(row.first_move), session_move: num(row.session_move),
      settled_on: on, implied: num(row.implied),
      inside: typeof row.inside === "boolean" ? row.inside : null,
      has_page: hasPage(symbol),
    });
  }
  return { date: rows.length > 0 ? date : null, today, rows, settled };
}

/** Revenue the way a headline writes it: $10.51bn, $812m. */
export function headlineMoney(amount: number | null | undefined): string {
  if (amount == null || !Number.isFinite(amount)) return "—";
  const size = Math.abs(amount);
  const sign = amount < 0 ? "−" : "";
  if (size >= 1e9) return `${sign}$${(size / 1e9).toFixed(2)}bn`;
  if (size >= 1e6) return `${sign}$${Math.round(size / 1e6).toLocaleString("en-US")}m`;
  return `${sign}$${Math.round(size).toLocaleString("en-US")}`;
}

/** "today", "Wednesday", or "Nov 18" once the weekday would be ambiguous. */
export function dayWord(day: string | null, today: string): string {
  if (!day) return "";
  if (day === today) return "today";
  const when = new Date(`${day}T12:00:00Z`);
  if (daysBetween(day, today) < 7) {
    return when.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" });
  }
  return when.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** "9:21 AM" from the note's New York local stamp. */
export function clock(readAt: string | null): string | null {
  const found = readAt?.match(/T(\d{2}):(\d{2})/);
  if (!found) return null;
  const hour = Number(found[1]);
  return `${((hour + 11) % 12) + 1}:${found[2]} ${hour < 12 ? "AM" : "PM"}`;
}
