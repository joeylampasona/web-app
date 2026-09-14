/**
 * Which moving averages a chart can honestly draw, decided once.
 *
 * Three of the four need nothing but the bars already on screen: a 9, 21 or 50
 * day average over 140 sessions is arithmetic the browser can do. Only the 200
 * needs help, because 140 bars cannot produce a 200-day average — the pipeline
 * publishes that one line pre-computed from the full history.
 *
 * The first version of this gated all four behind the published 200. A stock
 * whose data was published before the feature existed therefore got a legend
 * naming four lines and a chart containing none of them — the exact silent
 * failure this codebase keeps having to stamp out. So the decision lives here,
 * returns its reasons, and both the chart and the key read the same answer.
 */

export const MA_WINDOWS = [9, 21, 50, 200] as const;
export type MaWindow = (typeof MA_WINDOWS)[number];

/** A line the chart will draw, with its values aligned to the bars. */
export interface MaSeries {
  window: MaWindow;
  values: (number | null)[];
  /** Heavier as the window lengthens, so the four stay separable without
   *  depending on colour alone. */
  weight: 1 | 2;
}

/** A line the chart will not draw, and the reason a reader would accept. */
export interface MaMissing {
  window: MaWindow;
  reason: string;
}

export interface MaPlan {
  drawn: MaSeries[];
  missing: MaMissing[];
}

const WEIGHT: Record<MaWindow, 1 | 2> = { 9: 1, 21: 1, 50: 2, 200: 2 };

/** The same average the pipeline computes, on the values handed in.
 *  Null until there is enough history, so a line begins where its data does. */
export function simpleMovingAverage(values: number[], window: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (window <= 0 || values.length < window) return out;
  let running = 0;
  for (let i = 0; i < values.length; i++) {
    running += values[i];
    if (i >= window) running -= values[i - window];
    if (i >= window - 1) out[i] = running / window;
  }
  return out;
}

function drawable(values: (number | null)[]): boolean {
  let seen = 0;
  for (const value of values) {
    if (value !== null && value !== undefined && (seen += 1) >= 2) return true;
  }
  return false;
}

/**
 * @param closes      Closing prices of the bars on screen, in order.
 * @param published200 The pipeline's 200-day line for those same bars.
 *   `undefined` means the stock's published file has no such field — it was
 *   written before moving averages existed, and a fresh run will add it.
 *   `[]` means the field is there and empty — the stock has under a year of
 *   daily history, so the average genuinely does not exist. Those are
 *   different facts and the reader is told which one applies.
 */
export function planMovingAverages(
  closes: number[],
  published200: (number | null)[] | null | undefined,
): MaPlan {
  const drawn: MaSeries[] = [];
  const missing: MaMissing[] = [];

  // Slowest first, so a fast line crossing a slow one is drawn on top of it
  // rather than hidden underneath.
  const published = published200 ?? null;
  if (published === null) {
    missing.push({
      window: 200,
      reason: "not in this stock's published data yet — the next nightly run adds it",
    });
  } else if (published.length === 0) {
    missing.push({
      window: 200,
      reason: "this stock has under a year of daily history",
    });
  } else if (published.length !== closes.length) {
    // Both are tails of the same series and must line up. If they ever do not,
    // drawing the line would put every point on the wrong day.
    missing.push({
      window: 200,
      reason: `does not line up with the bars (${published.length} values for `
        + `${closes.length} sessions), so it is not drawn`,
    });
  } else if (!drawable(published)) {
    missing.push({ window: 200, reason: "this stock has under a year of daily history" });
  } else {
    drawn.push({ window: 200, values: published, weight: WEIGHT[200] });
  }

  for (const window of [50, 21, 9] as const) {
    const values = simpleMovingAverage(closes, window);
    if (drawable(values)) {
      drawn.push({ window, values, weight: WEIGHT[window] });
    } else {
      missing.push({
        window,
        reason: `needs ${window} sessions and this chart has ${closes.length}`,
      });
    }
  }

  missing.sort((a, b) => a.window - b.window);
  return { drawn, missing };
}
