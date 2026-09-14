import type { MaPlan, MaWindow } from "@/lib/movingAverages";

/**
 * Which line is which.
 *
 * Four lines on one chart is three too many to remember, and the site already
 * spends its one accent on the pivot — so none of these can be amber and none
 * of them can be guessed at from colour alone. The key carries the number.
 *
 * It also carries the absences. An earlier version listed all four whatever the
 * chart had actually drawn, which is how a stock with no published 200-day line
 * came to show a key for four lines above a chart with none. A key that names a
 * line the chart does not contain is worse than no key.
 */
const NOTE: Record<MaWindow, string> = {
  9: "about two weeks",
  21: "about a month",
  50: "about a quarter",
  200: "about a year",
};

export function MovingAverageKey({ plan, stacked }: {
  plan: MaPlan;
  /** Whether the pipeline found all four in order on the full history. Left
   *  undefined when the stock is not on a screen and so has no trend reading. */
  stacked?: boolean;
}) {
  return (
    <div className="stack" style={{ gap: "var(--gap-xs)" }}>
      <div className="row wrap" style={{ gap: "var(--gap-md)" }}>
        {plan.drawn
          .slice()
          .sort((a, b) => a.window - b.window)
          .map(({ window, weight }) => (
            <span key={window} className="row caption"
                  style={{ gap: 6, color: "var(--text-secondary)" }}>
              <span aria-hidden style={{
                width: 14, height: weight, borderRadius: 1, flexShrink: 0,
                background: `var(--chart-ma-${window})`,
              }} />
              <span className="num">{window}-day</span>
              <span className="dim">{NOTE[window]}</span>
            </span>
          ))}
      </div>

      {plan.missing.map(({ window, reason }) => (
        <p key={window} className="caption dim" style={{ margin: 0 }}>
          No {window}-day line: {reason}.
        </p>
      ))}

      {/* The pipeline's reading is about all four over the full history, so it
          would be misleading next to a chart that is missing one of them. */}
      {stacked !== undefined && plan.missing.length === 0 && (
        <p className="caption dim" style={{ margin: 0 }}>
          {stacked
            ? "All four are in order, fastest above slowest — every timeframe "
              + "pointing the same way."
            : "The four are not in order. That is a description of where the "
              + "averages sit, not a view about what happens next."}
        </p>
      )}
    </div>
  );
}
