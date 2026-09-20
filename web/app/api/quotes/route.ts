import { NextResponse } from "next/server";

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
// The producer runs every fifteen minutes. Re-fetching more often than that
// costs requests and cannot return anything newer.
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

  return NextResponse.json(
    {
      quotes: body.quotes ?? {},
      count: body.count ?? 0,
      fetched_at: body.fetched_at ?? null,
      note: body.note ?? null,
    },
    { headers: { "Cache-Control": `public, max-age=${CACHE_SECONDS}` } },
  );
}
