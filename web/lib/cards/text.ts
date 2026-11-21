import "server-only";
import { postText } from "@/lib/share";
import type { FigureCard } from "./base";

function sentenceCase(caps: string): string {
  // "FRIDAY CLOSE · NOV 20, 2026" as it would be written in a sentence.
  return caps.toLowerCase().replace(/(^|· )([a-z])/g, (_, lead, letter) => lead + letter.toUpperCase());
}

/**
 * A card as a few lines of text, from the card itself.
 *
 * Built from the same object the picture is drawn from, so the words a
 * reader copies and the image a link unfurls into cannot say different
 * things about the same night.
 */
export function cardText(card: FigureCard): string {
  const headline = `${card.lead ?? ""}${card.marked}${card.tail ?? ""}`;
  const figures = (card.cells ?? []).map((cell) =>
    cell.label === cell.value ? cell.label : `${cell.label} ${cell.value}`);
  const bars = (card.bars ?? []).map((bar) => `${bar.label} ${bar.value}`);
  return postText([
    `The Tape · ${sentenceCase(card.dateline)}`,
    // The kicker says what the headline is about, which the picture shows by
    // position and a line of text has to say outright.
    card.kicker,
    headline,
    figures.join(" · "),
    bars.join(" · "),
  ], card.path);
}
