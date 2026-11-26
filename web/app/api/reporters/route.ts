import fs from "node:fs";
import { NextResponse } from "next/server";
import { listStocks } from "@/lib/data";
import { newYorkToday, publicReporters } from "@/lib/reporters";

/**
 * The earnings reactions, proxied from the reporters job's note.
 *
 * Read the same way the delayed prices are (see ../quotes/route.ts): from a
 * branch of the repository, through this route rather than from the reader's
 * browser, carrying a token once the repository is private. The note is
 * rewritten at the job's two daily runs, so the page that reads this is
 * current between nightly builds.
 *
 * The note is the job's own memory and holds more than a reader should get:
 * who it has named, which filings it has read, which reactions wait on a
 * session. Only `date`, `rows` and `settled` leave here, field by field.
 *
 * Failure is not an error. The Earnings page is complete without this
 * section, so a missing or unreadable note answers with an empty set and the
 * section does not render.
 *
 * Configuration, all shared with the quotes route except the branch:
 *   QUOTES_REPO        owner/name, default joeylampasona/web-app
 *   QUOTES_TOKEN       a token with read access, once the repository is private
 *   REPORTERS_BRANCH   default "reporters"
 *   REPORTERS_FILE     a local path to read instead, for previewing the page
 *                      against a sample note. Never set in production.
 */
export const dynamic = "force-dynamic";
export const revalidate = 0;
const CACHE_SECONDS = 60;

const REPO = process.env.QUOTES_REPO ?? "joeylampasona/web-app";
const BRANCH = process.env.REPORTERS_BRANCH ?? "reporters";

function source(): string {
  return `https://raw.githubusercontent.com/${REPO}/${BRANCH}/reporters.json`;
}

// Which companies have a page, read once per server instance. The tree is
// fixed for the life of a deployment.
let pages: Set<string> | null = null;
function hasPage(symbol: string): boolean {
  if (pages === null) pages = new Set(listStocks());
  return pages.has(symbol);
}

export async function GET() {
  let note: unknown = null;
  const local = process.env.REPORTERS_FILE;
  if (local) {
    try {
      note = JSON.parse(fs.readFileSync(local, "utf-8"));
    } catch {
      note = null;
    }
  } else {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (process.env.QUOTES_TOKEN) {
      headers.Authorization = `Bearer ${process.env.QUOTES_TOKEN}`;
    }
    try {
      const response = await fetch(source(), {
        headers,
        next: { revalidate: CACHE_SECONDS },
      });
      if (response.ok) note = await response.json();
    } catch {
      note = null;
    }
  }

  return NextResponse.json(
    publicReporters(note, hasPage, newYorkToday()),
    { headers: { "Cache-Control": `public, max-age=${CACHE_SECONDS}` } },
  );
}
