import type { AnchoredVwap, Bar } from "./types";

/**
 * An anchored VWAP as a line over the bars the page already has.
 *
 * The pipeline publishes the figure and the anchor date, not the line: the
 * browser holds the bars and can draw it, the same way it draws the 9, 21
 * and 50-day averages. For an anchor older than the first bar here the
 * pipeline also sends the running totals up to that bar, and the line picks
 * up from them.
 *
 * It is a daily approximation. Each session contributes its typical price,
 * (high + low + close) / 3, weighted by its volume. A VWAP from every trade
 * would differ a little, most on the anchor day itself.
 */
export function anchoredLine(bars: Bar[], row: AnchoredVwap): (number | null)[] {
  let money = row.seed_money || 0;
  let volume = row.seed_volume || 0;
  const seeded = volume > 0;
  return bars.map((bar) => {
    if (!seeded && bar.time.slice(0, 10) < row.from) return null;
    if (bar.volume > 0) {
      money += ((bar.high + bar.low + bar.close) / 3) * bar.volume;
      volume += bar.volume;
    }
    return volume > 0 ? money / volume : null;
  });
}

/** The row for one anchor, if the stock has it. */
export function anchorOf(rows: AnchoredVwap[] | null | undefined,
                         kind: AnchoredVwap["anchor"]): AnchoredVwap | null {
  return (rows ?? []).find((row) => row.anchor === kind) ?? null;
}
