import { NextResponse } from "next/server";
import { fetchLiveQuote, worthAsking, type LiveQuote } from "@/lib/cboeQuote";
import { getIndexes } from "@/lib/data";

/**
 * The delayed intraday prices, proxied.
 *
 * Proxied rather than fetched straight from the browser for two reasons. The
 * site makes no third-party requests from a reader's browser today, and a
 * price ticker is a poor reason to start telling someone else's server who is
 * reading which page. And the quotes branch will stop being publicly readable
 * the moment this repository goes private, at which point a direct fetch
 * breaks and this route keeps working by carrying a token.
 *
 * Failure here is not an error. The pages this feeds all render correctly from
 * the closing figures alone — the quotes only sharpen them — so an outage
 * returns an empty set and the site quietly shows yesterday's close, which is
 * what it showed before any of this existed.
 */
export const dynamic = "force-dynamic";
// The sweep runs on a schedule. Re-fetching its file faster cannot return
// anything newer; the live half below has its own, shorter window.
export const revalidate = 0;
const CACHE_SECONDS = 60;

const REPO = process.env.QUOTES_REPO ?? "joeylampasona/web-app";
const BRANCH = process.env.QUOTES_BRANCH ?? "quotes";

function source(): string {
  return `https://raw.githubusercontent.com/${REPO}/${BRANCH}/quotes.json`;
}

export async function GET() {
  const headers: Record<string, string> = { Accept: "application/json" };
  // Set once the repository is private. Absent, the public raw URL is used.
  if (process.env.QUOTES_TOKEN) {
    headers.Authorization = `Bearer ${process.env.QUOTES_TOKEN}`;
  }

  let payload: unknown = null;
  try {
    const response = await fetch(source(), {
      headers,
      next: { revalidate: CACHE_SECONDS },
    });
    if (response.ok) payload = await response.json();
  } catch {
    payload = null;
  }

  const body = (payload ?? { quotes: {}, count: 0, fetched_at: null }) as {
    quotes?: Record<string, unknown>;
    count?: number;
    fetched_at?: string | null;
    note?: string;
  };

  const quotes: Record<string, unknown> = { ...(body.quotes ?? {}) };

  // The index symbols, read live and laid over the top.
  //
  // These are the two largest numbers on the site and they are the first thing
  // anybody uses to decide whether it is running. Everything else here comes
  // from a scheduled sweep, and GitHub delivered two of roughly thirty-six
  // scheduled runs on the day this was written — so SPY and QQQ showed
  // Friday's close all through Monday. Two requests take about as long as the
  // one this route already makes, so they do not need a schedule at all.
  //
  // Which symbols is not hardcoded: it is whichever ones the nightly put in
  // indexes.json, because that is exactly the set the page renders.
  let liveAt: string | null = null;
  const symbols = (getIndexes()?.rows ?? []).map((row) => row.symbol);
  if (symbols.length > 0 && worthAsking()) {
    const fetched = await Promise.all(
      symbols.map(async (symbol) =>
        [symbol, await fetchLiveQuote(symbol)] as const),
    );
    const live = fetched.filter((pair): pair is [string, LiveQuote] =>
      pair[1] !== null);
    for (const [symbol, quote] of live) quotes[symbol] = quote;
    // Only when something actually arrived. A timestamp on a set that came
    // entirely from the sweep would date the page to now and be a lie about
    // every number in it.
    if (live.length > 0) liveAt = new Date().toISOString();
  }

  return NextResponse.json(
    {
      quotes,
      count: Object.keys(quotes).length,
      fetched_at: body.fetched_at ?? null,
      // When the live half was read, which is not when the sweep ran. Kept
      // separate so the page can date each number to the moment it belongs
      // to rather than showing one time over two different readings.
      live_at: liveAt,
      live_symbols: liveAt ? symbols : [],
      note: body.note ?? null,
    },
    { headers: { "Cache-Control": `public, max-age=${CACHE_SECONDS}` } },
  );
}
