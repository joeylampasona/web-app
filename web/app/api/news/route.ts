import { NextResponse } from "next/server";

/**
 * Headlines published since the nightly, proxied from the quotes branch.
 *
 * The hourly quotes run writes them beside the prices. Proxied for the same
 * reasons as the quotes: no third-party request from a reader's browser, and
 * the branch stops being publicly readable once the repository is private.
 * Failure returns an empty list, and the pages show the nightly's headlines,
 * which is what they showed before this existed.
 */
export const dynamic = "force-dynamic";
export const revalidate = 0;
const CACHE_SECONDS = 300;

const REPO = process.env.QUOTES_REPO ?? "joeylampasona/web-app";
const BRANCH = process.env.QUOTES_BRANCH ?? "quotes";

export async function GET() {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (process.env.QUOTES_TOKEN) headers.Authorization = `Bearer ${process.env.QUOTES_TOKEN}`;
  let body: { fetched_at?: string | null; articles?: unknown[] } | null = null;
  try {
    const response = await fetch(
      `https://raw.githubusercontent.com/${REPO}/${BRANCH}/news_live.json`,
      { headers, next: { revalidate: CACHE_SECONDS } });
    if (response.ok) body = await response.json();
  } catch {
    body = null;
  }
  return NextResponse.json(
    { fetched_at: body?.fetched_at ?? null, articles: body?.articles ?? [] },
    { headers: { "Cache-Control": `public, max-age=${CACHE_SECONDS}` } },
  );
}
