import type { StructureCheckRow } from "@/lib/types";

/**
 * Why a stock is on none of the screens, measured.
 *
 * The page used to say "Not on a screen at the moment — no base, so no pivot
 * to draw", which is a guess dressed as a fact. Plenty of these names have a
 * perfectly good base that is two weeks short of the minimum, or sit 30% under
 * a pivot that is genuinely there. Those are different situations, and someone
 * who looked this company up specifically is the reader most likely to care
 * which one it is.
 *
 * Three states, not two. `met: null` means the check could not be run at all —
 * you cannot measure a base's depth when there is no base — and printing that
 * as a failure would invent verdicts out of one absence.
 */
function mark(met: boolean | null) {
  if (met === null) return { dot: "var(--border-stronger)", text: "var(--text-muted)", glyph: "–" };
  if (met) return { dot: "var(--gain)", text: "var(--text-primary)", glyph: "✓" };
  return { dot: "var(--loss)", text: "var(--text-primary)", glyph: "✕" };
}

export function StructureCheck({ rows, name }: {
  rows: StructureCheckRow[] | null | undefined;
  name: string;
}) {
  if (!rows || rows.length === 0) {
    return (
      <div className="card muted footnote">
        Not on a screen at the moment. There is too little price history to say
        why — the checks below need about six weeks of trading.
      </div>
    );
  }

  const failed = rows.filter((row) => row.met === false);
  // Naming the binding constraint in one line, above the list, because that is
  // the whole answer for most names and the list is the evidence for it.
  const headline = failed.length === 0
    ? `${name} passes every check below but is not on a screen — the screens also ` +
      `require the base to be the most recent structure, which this one is not.`
    : failed.length === 1
      ? `${name} is off the screens on one check: ${failed[0].label.toLowerCase()}.`
      : `${name} is off the screens on ${failed.length} checks.`;

  return (
    <div className="card stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="eyebrow">Why it is on no screen</div>
      <p className="footnote muted" style={{ margin: 0 }}>{headline}</p>
      <div className="stack" style={{ gap: "var(--gap-xs)" }}>
        {rows.map((row) => {
          const m = mark(row.met);
          return (
            <div key={row.label} className="row"
                 style={{ gap: "var(--gap-sm)", alignItems: "baseline" }}>
              <span aria-hidden className="num" style={{
                width: 12, flexShrink: 0, fontSize: 10, color: m.dot, textAlign: "center",
              }}>{m.glyph}</span>
              <span className="footnote" style={{ color: m.text, width: "10.5em", flexShrink: 0 }}>
                {row.label}
              </span>
              <span className="caption dim">{row.detail}</span>
            </div>
          );
        })}
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        Measured against the base-and-breakout thresholds. The other screens use
        their own numbers, so a name can miss here and still be a fair-looking
        chart.
      </p>
    </div>
  );
}
