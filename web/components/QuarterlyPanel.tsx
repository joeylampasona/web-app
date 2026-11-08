import { compactMoney } from "@/lib/format";
import type { QuarterlyFlag, QuarterlyRead } from "@/lib/types";

/**
 * The latest quarter as filed, read by fixed rules.
 *
 * Bars of revenue, free cash flow and net income for the last eight quarters,
 * the quarter at a glance, one flag per kind (growth, margin, profit, cash,
 * funding, balance) each with the threshold it crossed, and the lines the same
 * filing supports that a headline does not show, printed only when they pass
 * a threshold. Ported from the Market Desk's earnings reads, without its
 * summary sentence or its verdict: this panel says what the filing shows, not
 * what to make of it.
 */
function quarterLabel(iso: string): string {
  const d = new Date(`${iso}T12:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" });
}

function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function Bars({ title, values, labels }: {
  title: string; values: (number | null)[]; labels: string[];
}) {
  const known = values.filter((v): v is number => v != null);
  if (!known.length) return null;
  const hi = Math.max(0, ...known), lo = Math.min(0, ...known);
  const span = hi - lo || 1;
  const W = 100, H = 60, gap = 2;
  const w = (W - gap * (values.length - 1)) / values.length;
  const zero = (hi / span) * H;
  const last = values[values.length - 1];
  return (
    <div className="card stack" style={{ gap: "var(--gap-xs)", padding: "var(--pad-sm) var(--pad-md)" }}>
      <div className="between">
        <span className="caption muted">{title}</span>
        <span className="num caption">{last == null ? "—" : compactMoney(last)}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={60} preserveAspectRatio="none"
           role="img"
           aria-label={`${title} by quarter: ${values.map((v, i) => `${labels[i]} ${v == null ? "none filed" : compactMoney(v)}`).join(", ")}`}>
        <line x1={0} x2={W} y1={zero} y2={zero} stroke="var(--border-strong)" strokeWidth={0.5}
              vectorEffect="non-scaling-stroke" />
        {values.map((v, i) => {
          if (v == null) return null;
          const h = (Math.abs(v) / span) * H;
          return (
            <rect key={labels[i]} x={i * (w + gap)} width={w}
                  y={v >= 0 ? zero - h : zero} height={Math.max(h, 0.5)}
                  fill={v >= 0 ? "var(--gain)" : "var(--loss)"} opacity={i === values.length - 1 ? 1 : 0.6} />
          );
        })}
      </svg>
      <div className="between caption dim">
        <span>{labels[0]}</span><span>{labels[labels.length - 1]}</span>
      </div>
    </div>
  );
}

const MARK: Record<QuarterlyFlag["tone"], { glyph: string; cls: string }> = {
  good: { glyph: "▲", cls: "badge badge--gain" },
  bad: { glyph: "▼", cls: "badge badge--loss" },
  neutral: { glyph: "•", cls: "badge" },
};

export function QuarterlyPanel({ q }: { q: QuarterlyRead | null | undefined }) {
  if (!q) return null;
  const g = q.glance;
  const labels = q.bars.map((b) => quarterLabel(b.end));
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="footnote muted">
        The quarter to {new Date(`${g.end}T12:00:00Z`).toLocaleDateString("en-US", {
          month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}
      </div>
      <div className="grid-3">
        <Bars title="Revenue" values={q.bars.map((b) => b.revenue)} labels={labels} />
        <Bars title="Free cash flow" values={q.bars.map((b) => b.fcf)} labels={labels} />
        <Bars title="Net income" values={q.bars.map((b) => b.net_income)} labels={labels} />
      </div>
      <p className="caption" style={{ margin: 0 }}>
        Revenue {g.revenue == null ? "—" : compactMoney(g.revenue)}, {pct(g.revenue_qoq)} on
        the quarter and {pct(g.revenue_yoy)} on a year ago
        {g.gross_margin != null && (
          <>; gross margin {g.gross_margin.toFixed(1)}%
            {g.gross_margin_move != null && <> ({g.gross_margin_move > 0 ? "+" : ""}{g.gross_margin_move.toFixed(1)} points)</>}
          </>
        )}
        {g.shares_yoy != null && <>; share count {pct(g.shares_yoy)} on a year ago</>}.
      </p>
      {q.flags.length > 0 && (
        <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
          {q.flags.map((f) => (
            <span key={`${f.kind}-${f.text}`} className={MARK[f.tone].cls}>
              <span aria-hidden>{MARK[f.tone].glyph}</span> {f.text}
            </span>
          ))}
        </div>
      )}
      {q.notes.length > 0 && (
        <div className="stack" style={{ gap: "var(--gap-xs)" }}>
          <div className="caption muted">Not obvious from the headline</div>
          <ul className="caption" style={{ margin: 0, paddingLeft: "1.1em" }}>
            {q.notes.map((n) => <li key={n}>{n}</li>)}
          </ul>
        </div>
      )}
      <p className="caption dim" style={{ margin: 0 }}>
        From the company&rsquo;s 10-Q and 10-K filings. Flags are fixed rules:
        revenue 20% or more up on a year ago, or 5% down; gross margin a point
        or more either way; a profit or a loss and which way it moved; free cash
        flow and its runway; capital spending above operating cash flow, the
        share count 5% higher, or buybacks; net cash or net debt. Notes appear
        only past a threshold. Neither is a verdict on the quarter.
      </p>
    </div>
  );
}
