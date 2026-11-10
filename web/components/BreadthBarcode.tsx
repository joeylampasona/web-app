import type { BreadthBarcode as Barcode } from "@/lib/types";

/**
 * The market as a barcode: one tick per stock, strongest on the left.
 *
 * Each tick is tinted by where the stock sits against its 50 and 200-day
 * lines. Read left to right it shows how far down the ranking a healthy
 * trend reaches: a strip green two thirds of the way across is a broad
 * market, one green for a sliver at the left is a few leaders carrying it.
 * The share above both lines in each tenth is printed underneath, because the
 * picture is the shape and the numbers are the reading.
 */
const FILL: Record<string, string> = {
  "3": "var(--gain)",
  "2": "rgba(var(--heat-up), 0.4)",
  "1": "rgba(var(--heat-down), 0.4)",
  "0": "var(--loss)",
};
const ORDER = ["3", "2", "1", "0"];

export function BreadthBarcode({ strip }: { strip: Barcode | null }) {
  if (!strip || !strip.n) return null;
  // Adjacent ticks in the same state are one rectangle: a few hundred
  // elements instead of a few thousand, and the same picture.
  const runs: { state: string; x: number; w: number }[] = [];
  for (let i = 0; i < strip.ticks.length; i++) {
    const state = strip.ticks[i];
    const last = runs[runs.length - 1];
    if (last && last.state === state) last.w += 1;
    else runs.push({ state, x: i, w: 1 });
  }
  const pct = (k: string) => Math.round((100 * (strip.counts[k] ?? 0)) / strip.n);
  return (
    <section className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="ruled-head">
        <h2>The market as a barcode</h2>
        <span className="kicker">{strip.n.toLocaleString("en-US")} stocks · strongest on the left</span>
      </div>
      <svg viewBox={`0 0 ${strip.n} 10`} width="100%" height={64} preserveAspectRatio="none"
           shapeRendering="crispEdges" role="img" className="barcode"
           aria-label={`Every ranked stock by trend, strongest first: ${ORDER.map((k) =>
             `${pct(k)}% ${strip.labels[k].toLowerCase()}`).join(", ")}`}>
        {runs.map((r) => (
          <rect key={r.x} x={r.x} y={0} width={r.w} height={10} fill={FILL[r.state]} />
        ))}
      </svg>
      <div className="barcode-tenths" aria-hidden>
        {strip.healthy_by_tenth.map((v, i) => (
          <span key={i} className="num caption">{v == null ? "—" : `${v}%`}</span>
        ))}
      </div>
      <div className="between caption dim">
        <span>RS 99</span>
        <span>Share above both lines, in each tenth of the ranking</span>
        <span>RS 1</span>
      </div>
      <div className="row wrap caption" style={{ gap: "6px var(--gap-lg)" }}>
        {ORDER.map((k) => (
          <span key={k} className="row" style={{ gap: 6 }}>
            <span aria-hidden className="scale-key" style={{ background: FILL[k] }} />
            {strip.labels[k]} <span className="num dim">{pct(k)}%</span>
          </span>
        ))}
      </div>
    </section>
  );
}
