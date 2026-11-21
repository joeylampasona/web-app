import { figureCard } from "@/lib/cards/base";
import { screenCard } from "@/lib/cards/cards";
import { getAllScreens } from "@/lib/data";

/** One screen's card: the pattern, its drawing and tonight's counts by stage. */
export const runtime = "nodejs";
export const dynamic = "force-static";

export function generateStaticParams() {
  return getAllScreens().map((screen) => ({ screen: `${screen.screen}.png` }));
}

export async function GET(_: Request, { params }: { params: Promise<{ screen: string }> }) {
  const { screen } = await params;
  const found = screenCard(screen.replace(/\.png$/, ""));
  if (!found) return new Response("No such screen.", { status: 404 });
  return figureCard(found);
}
