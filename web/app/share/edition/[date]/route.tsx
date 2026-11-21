import { figureCard } from "@/lib/cards/base";
import { editionCard } from "@/lib/cards/cards";

/**
 * A back issue's card: that night's read as it was published.
 *
 * Drawn the first time it is asked for and kept, rather than all at build.
 * The archive runs to a year of nights and almost none will ever be shared.
 */
export const runtime = "nodejs";
export const dynamic = "force-static";

export async function GET(_: Request, { params }: { params: Promise<{ date: string }> }) {
  const { date } = await params;
  const day = date.replace(/\.png$/, "");
  const found = /^\d{4}-\d{2}-\d{2}$/.test(day) ? editionCard(day) : null;
  if (!found) return new Response("No such edition.", { status: 404 });
  return figureCard(found);
}
