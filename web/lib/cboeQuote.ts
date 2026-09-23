/**
 * One delayed price, fetched server-side at request time.
 *
 * The nightly sweep covers the names on a screen and takes six minutes, which
 * is why it lives in a scheduled job. Two symbols take about two hundred
 * milliseconds, which means the numbers at the top of the home page do not
 * need a schedule at all — and that matters, because GitHub delivered two of
 * roughly thirty-six scheduled runs the day this was written, so those two
 * numbers showed Friday's close all through Monday.
 *
 * Deliberately a copy of catalysts/cboe.py's `quote()`, field for field. The
 * two read the same endpoint and must agree about what it means; if that
 * function changes, this one changes with it.
 */

export interface LiveQuote {
  last: number;
  prev_close: number | null;
  change_pct: number | null;
  at: string | null;
}

const QUOTE_BASE = "https://cdn.cboe.com/api/global/delayed_quotes/quotes";

/** Under a minute, so a reader refreshing sees movement, and one request per
 *  window however many people are looking. Next's data cache dedupes these
 *  across requests even though the route itself is dynamic. */
export const LIVE_CACHE_SECONDS = 45;

/** Cboe's spelling of a ticker. Class shares lose the dot: BRK.B is BRKB. */
export function endpointSymbol(symbol: string): string {
  return symbol.trim().toUpperCase().replace(/[.-]/g, "");
}

function num(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

/**
 * True when a US session is plausibly running or close to it.
 *
 * Not a correctness gate — Cboe answers at three in the morning with the last
 * close, which is right. It exists so a weekend does not spend thousands of
 * requests on somebody else's free endpoint to learn Friday's number again.
 */
export function worthAsking(now: Date = new Date()): boolean {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "numeric",
    hour12: false,
  }).formatToParts(now);
  const weekday = parts.find((p) => p.type === "weekday")?.value ?? "";
  const hour = Number(parts.find((p) => p.type === "hour")?.value ?? "-1");
  if (weekday === "Sat" || weekday === "Sun") return false;
  // 4am to 9pm New York: pre-market through the end of the after-hours
  // session, which is when the number can still differ from the close.
  return hour >= 4 && hour <= 20;
}

/**
 * The endpoint's `data` object, mapped. Separated from the fetch so it can be
 * checked against the Python line for line without a network.
 */
export function mapQuote(data: Record<string, unknown>): LiveQuote | null {
  // current_price during the session, close outside it. Same order as the
  // Python, which found current_price absent on some names.
  const last = num(data.current_price) || num(data.close);
  if (last <= 0) return null;

  const previous = num(data.prev_day_close);
  return {
    last: Math.round(last * 1e4) / 1e4,
    prev_close: previous > 0 ? Math.round(previous * 1e4) / 1e4 : null,
    // Null rather than zero when there is nothing to compare against.
    // "unknown" must not render as "unchanged".
    change_pct: previous > 0
      ? Math.round((last / previous - 1) * 1e4) / 100
      : null,
    at: typeof data.last_trade_time === "string" ? data.last_trade_time : null,
  };
}

export async function fetchLiveQuote(symbol: string): Promise<LiveQuote | null> {
  try {
    const response = await fetch(`${QUOTE_BASE}/${endpointSymbol(symbol)}.json`, {
      headers: { Accept: "application/json" },
      next: { revalidate: LIVE_CACHE_SECONDS },
    });
    if (!response.ok) return null;
    return mapQuote((await response.json())?.data ?? {});
  } catch {
    // Every page this feeds renders from the closing figures alone. An outage
    // here costs sharpness, not correctness.
    return null;
  }
}
