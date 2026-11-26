import "server-only";
import fs from "node:fs";
import { listStocks } from "@/lib/data";
import { newYorkToday, publicReporters, type ReportersPayload } from "@/lib/reporters";

/**
 * The day's earnings reactions, for the MCP tools.
 *
 * Read from the same place, with the same configuration, as the site's own
 * /api/reporters route, and passed through the same `publicReporters`, which
 * copies out `date`, `rows` and `settled` field by field and nothing else.
 * So what a reader's AI is told is what the Earnings page shows, and the
 * job's private notes (who it has named, which filings it has read, what is
 * still waiting on a session) never leave here either.
 *
 * A missing or unreadable note is an empty answer, not an error.
 */
const REPO = process.env.QUOTES_REPO ?? "joeylampasona/web-app";
const BRANCH = process.env.REPORTERS_BRANCH ?? "reporters";
const CACHE_SECONDS = 60;

let pages: Set<string> | null = null;
function hasPage(symbol: string): boolean {
  if (pages === null) pages = new Set(listStocks());
  return pages.has(symbol);
}

export async function readReporters(): Promise<ReportersPayload> {
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
    if (process.env.QUOTES_TOKEN) headers.Authorization = `Bearer ${process.env.QUOTES_TOKEN}`;
    try {
      const response = await fetch(
        `https://raw.githubusercontent.com/${REPO}/${BRANCH}/reporters.json`,
        { headers, next: { revalidate: CACHE_SECONDS } });
      if (response.ok) note = await response.json();
    } catch {
      note = null;
    }
  }
  return publicReporters(note, hasPage, newYorkToday());
}
