import "server-only";
import { SharePage } from "@/components/SharePage";
import type { FigureCard } from "./base";
import { cardText } from "./text";

/**
 * The share row for a page that has a card, filled in from the card.
 *
 * Renders nothing when the page has no card tonight: a button that fetches a
 * picture which is not there is worse than no button.
 */
export function PageShare({ card, image, title }: {
  card: FigureCard | null;
  /** The card's address: "/share/breadth.png". */
  image: string;
  title: string;
}) {
  if (!card) return null;
  return <SharePage path={card.path} title={title} card={image} text={cardText(card)} />;
}
