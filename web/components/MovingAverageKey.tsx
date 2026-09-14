/**
 * Which line is which.
 *
 * Four lines on one chart is three too many to remember, and the site already
 * spends its one accent on the pivot — so none of these can be amber and none
 * of them can be guessed at from colour alone. The key carries the number.
 */
const LINES: { window: number; note: string; weight: number }[] = [
  { window: 9, note: "about two weeks", weight: 1 },
  { window: 21, note: "about a month", weight: 1 },
  { window: 50, note: "about a quarter", weight: 2 },
  { window: 200, note: "about a year", weight: 2 },
];

export function MovingAverageKey({ stacked }: { stacked?: boolean }) {
  return (
    <div className="stack" style={{ gap: "var(--gap-xs)" }}>
      <div className="row wrap" style={{ gap: "var(--gap-md)" }}>
        {LINES.map(({ window, note, weight }) => (
          <span key={window} className="row caption"
                style={{ gap: 6, color: "var(--text-secondary)" }}>
            <span aria-hidden style={{
              width: 14, height: weight, borderRadius: 1, flexShrink: 0,
              background: `var(--chart-ma-${window})`,
            }} />
            <span className="num">{window}-day</span>
            <span className="dim">{note}</span>
          </span>
        ))}
      </div>
      {stacked !== undefined && (
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
