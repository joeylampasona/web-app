/**
 * Plain-English copy for every (i) on the site.
 *
 * Two rules hold everywhere in this file:
 *   - No metric is ever defined as predictive. These say what a number measures,
 *     not what it implies about the future.
 *   - The words buy, sell, target and recommendation do not appear, with the
 *     single exception of the Learn page's step-1 label, which describes the
 *     method rather than instructing the reader.
 */

const COPY = {
  "metric.rs_rating":
    "Where this stock's 3, 6 and 12-month return ranks against every other name in " +
    "our universe, from 1 to 99. A reading of 92 means it outran 92% of them. New " +
    "listings without twelve months of history read \"not ranked yet\" instead of a " +
    "number.",
  "metric.now_vs_pivot":
    "How far today's close sits from the pivot, as a percentage. Negative means it " +
    "is still underneath.",
  "metric.tightening":
    "The average daily range in the first half of the base divided by the second " +
    "half. Above 1 means the swings got smaller as the base went on.",
  "metric.volume_dryup":
    "Shares traded in the first half of the base divided by the second half. Above " +
    "1 means fewer shares changed hands as the base went on.",
  "metric.up_down_volume":
    "Volume on up days minus volume on down days over the last 50 sessions, divided " +
    "by the total. Runs from −1 to +1. It describes which side has been heavier, " +
    "nothing more.",
  "metric.from_52w_high":
    "How far below its highest price of the last year the stock is trading.",
  "metric.price_vs_50ma":
    "How far today's close is above or below the average closing price of the last " +
    "50 sessions.",
  "metric.breakout_day_gain":
    "How much the stock moved on the session it closed above the pivot.",
  "metric.one_day_gain": "How much it moved in the most recent session.",
  "metric.breakout_volume":
    "Volume on the breakout session as a multiple of its own average over the " +
    "previous 50 sessions.",
  "metric.close_in_range":
    "Where the close landed inside that session's range, from 0 at the low to 1 at " +
    "the high.",
  "metric.base_weeks": "How many weeks the stock has been building this base.",
  "metric.base_depth":
    "How far price fell from the top of the base to its lowest point inside it.",
  "metric.pivot":
    "The ceiling at the top of the base — the price the stock would have to close " +
    "above for this to count as a breakout.",

  "flag.squat":
    "Price reached the pivot on heavy volume and closed in the lower part of the " +
    "day's range. Sellers met the move.",
  "flag.failed_poke":
    "Price pushed above the pivot during a session in the last two weeks and closed " +
    "back underneath it.",
  "flag.cooling":
    "The 9-day average crossed below the 21-day within the last two weeks, so " +
    "short-term momentum has eased. That is often a pause inside a move rather " +
    "than the end of one, which is why it is a marker here and not a stage.",

  "stage.forming": "The base is there and price is still under the pivot.",
  "stage.fresh_breakout": "It closed above the pivot within the last 5 sessions.",
  "stage.climbing": "It cleared the pivot earlier and is still above its trailing line.",
  "stage.played_out":
    "It broke out earlier this calendar year and has since stopped out or trailed " +
    "out. These stay published. A screen that only shows the ones that worked has " +
    "nothing to check it against.",

  "breadth.near_52w_highs": "Within 5% of the highest price of the last year.",
  "breadth.near_52w_lows": "Within 5% of the lowest price of the last year.",
  "breadth.confirmed_uptrend":
    "Above both the 50-day and 200-day lines, with the 50 above the 200.",
  "breadth.up_today": "Closed higher than the session before.",
  "breadth.above_50ma": "Above the average closing price of the last 50 sessions.",
  "breadth.above_200ma": "Above the average closing price of the last 200 sessions.",
  "breadth.breakouts":
    "Closed above the highest high of the prior 50 sessions. This is a market-wide " +
    "count and does not depend on which screen you are looking at.",
  "breadth.failed_pokes":
    "Pushed above that same level during the session and closed back under it.",

  "rotation.x": "Strength now: the group's RS rating, 1 to 99.",
  "rotation.y": "Momentum: how much that rating has moved since a month ago.",
  "rotation.quadrants":
    "Strong and improving is powering up. Weak and improving is turning up. Strong " +
    "and fading is cooling off. Weak and fading is falling back.",

  "iv.richness":
    "How much richer implied volatility is for the expiry that brackets the dated " +
    "event than for the expiries either side of it.",
  "iv.band":
    "A five-dot reading of that richness. High implied volatility is never itself a " +
    "catalyst — it is a pricing observation about a date that already exists.",

  "treemap.size": "Each tile is sized by the combined market value of its members.",
  "treemap.colour": "Colour is the change in the group's RS rating over the window you pick.",

  "screens.export": "Download the current list as a CSV.",
  "screens.sort": "Default is RS rating, the one filter with published support behind it.",
} as const;

export type CopyKey = keyof typeof COPY;

export function copy(key: CopyKey | string): string {
  return (COPY as Record<string, string>)[key] ?? "";
}

export const LEGAL =
  "A screening and market-analytics tool. Not investment advice. We are not a " +
  "registered investment adviser. Historical figures are backtests and are " +
  "hypothetical.";

/**
 * The site's name, in one place.
 *
 * It was written out in sixteen files — the header, the manifest, two preview
 * images, the share card, the disclaimer, and every page title — which is
 * sixteen chances to rename fifteen of them. SITE_NAME is the long form,
 * SITE_SHORT the one a phone home screen has room for.
 */
export const SITE_NAME = "Base & Breakout";
export const SITE_SHORT = "Breakout";

export const TAGLINE = "Bases, breakouts and relative strength, after every close.";

export const RS_NOTE =
  "Relative strength is the default sort because it is the only component of our " +
  "own out-of-sample study that carried statistical support. The base and pivot " +
  "work is a way of describing and timing a stock, not a claim that the shape " +
  "predicts a return.";
