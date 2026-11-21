import { figureCard } from "@/lib/cards/base";
import { PAGE_CARDS } from "@/lib/cards/cards";

/**
 * A page's share card at an address: /share/read.png, /share/breadth.png.
 *
 * An address rather than a file beside each page, because three things need
 * the same picture: the link preview, the page's own "Save card" button, and
 * the nightly's message, which is not a browser and can only be handed a URL.
 *
 * Drawn once at build, when the data is. A card is a picture of the close and
 * the close does not change until the next build replaces it.
 */
export const runtime = "nodejs";
export const dynamic = "force-static";

export function generateStaticParams() {
  return Object.keys(PAGE_CARDS).map((name) => ({ card: `${name}.png` }));
}

export async function GET(_: Request, { params }: { params: Promise<{ card: string }> }) {
  const { card } = await params;
  const build = PAGE_CARDS[card.replace(/\.png$/, "")];
  const found = build ? build() : null;
  if (!found) return new Response("No such card.", { status: 404 });
  return figureCard(found);
}
