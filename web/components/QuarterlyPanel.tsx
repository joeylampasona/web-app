import Link from "next/link";
import { compactMoney } from "@/lib/format";
import type { QuarterlyRead, ReadLine } from "@/lib/types";

/**
 * An earnings read: the latest filed quarter, in Market Desk's card.
 *
 * The takeaway sentence, four tiles at a glance, the rule flags ("what the
 * numbers say"), eight quarters of revenue, free cash flow and net income as
 * bars, the lines the filing supports that a headline does not ("what is not
 * obvious"), what Market Desk measured around the print, and the final read:
 * growth REAL, WEAK or FLAT and economic proof SHOWN or PENDING, with the
 * question those imply and the first weak flag as the next quarter's test.
 *
 * Every line is a fixed rule on the company's 10-Q and 10-K figures. The
 * takeaway and the final read are those rules' summary of the quarter, not a
 * view on the stock.
 */
function pct(v: number | null | undefined, digits = 1): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

function money(v: number | null | undefined): string {
  return v == null ? "—" : compactMoney(v);
}

function day(iso: string, opts: Intl.DateTimeFormatOptions): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", { ...opts, timeZone: "UTC" });
}

const TONE_CLASS = { 1: "read-good", 0: "read-neutral", "-1": "read-bad" } as const;
const MARK = { 1: "▲", 0: "·", "-1": "▼" } as const;

function Lines({ lines }: { lines: ReadLine[] }) {
  return (
    <ul className="read-lines">
      {lines.map((line) => (
        <li key={line.key + line.text}>
          <span aria-hidden className={TONE_CLASS[line.tone]}>{MARK[line.tone]}</span>
          <span className="visually-hidden">
            {line.tone === 1 ? "Good: " : line.tone === -1 ? "Weak: " : ""}
          </span>
          <span>{line.text}</span>
        </li>
      ))}
    </ul>
  );
}

function Tile({ label, value, chip, tone }: {
  label: string; value: string; chip?: string | null; tone?: 1 | 0 | -1;
}) {
  return (
    <div className="read-tile">
      <div className="caption muted">{label}</div>
      <div className="num read-tile-value">{value}</div>
      {chip && <span className={`read-chip ${tone == null ? "" : TONE_CLASS[tone]}`}>{chip}</span>}
    </div>
  );
}

function Bars({ title, values }: { title: string; values: (number | null)[] }) {
  const known = values.filter((v): v is number => v != null);
  if (!known.length) return null;
  const hi = Math.max(0, ...known), lo = Math.min(0, ...known);
  const span = hi - lo || 1;
  const W = 100, H = 34, gap = 3;
  const w = (W - gap * (values.length - 1)) / values.length;
  const zero = (hi / span) * H;
  return (
    <div className="stack" style={{ gap: 2, minWidth: 0, flex: "1 1 120px", maxWidth: 170 }}>
      <span className="caption muted">{title}</span>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none"
           role="img" aria-label={`${title}, last ${values.length} quarters`}>
        <line x1={0} x2={W} y1={zero} y2={zero} stroke="var(--border-strong)"
              strokeWidth={0.5} strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
        {values.map((v, i) => {
          if (v == null) return null;
          const h = Math.max((Math.abs(v) / span) * H, 0.8);
          const last = i === values.length - 1;
          return (
            <rect key={i} x={i * (w + gap)} width={w} y={v >= 0 ? zero - h : zero} height={h}
                  fill={v >= 0 ? "var(--gain)" : "var(--loss)"} opacity={last ? 1 : 0.5} />
          );
        })}
      </svg>
    </div>
  );
}

export function EarningsReadCard({ r, symbol, name, heading = true }: {
  r: QuarterlyRead;
  symbol?: string;
  name?: string;
  /** Off on a stock's own page, where the section already names the company. */
  heading?: boolean;
}) {
  const g = r.glance;
  const negatives = r.flags.filter((f) => f.tone === -1).length;
  const frame = negatives === 0 ? "read-good" : negatives <= 2 ? "read-warn" : "read-bad";
  const quarter = day(g.end, { month: "short", year: "numeric" });
  const d = r.desk;
  const deskParts: string[] = [];
  if (d?.surprise_pct != null) deskParts.push(`EPS ${pct(d.surprise_pct)} against the estimate`);
  if (d?.realised_pct != null) {
    deskParts.push(`moved ${pct(d.realised_pct)} on the print`
      + (d.implied_pct ? ` against ±${d.implied_pct.toFixed(1)}% priced` : ""));
  }
  if (d?.drift) deskParts.push(`${d.drift.replace("_", " ").toLowerCase()} drift signal since`);
  const fcfChip = g.fcf == null ? null
    : g.fcf > 0 ? "Cash generating"
    : `Burning${g.runway_q != null && g.runway_q < 40 ? ` · ${Math.max(1, Math.round(g.runway_q))}q runway` : ""}`;

  return (
    <article className="card stack read-card" style={{ gap: "var(--gap-md)" }}>
      {heading && (
        <header className="eyebrow" style={{ color: "var(--text-secondary)" }}>
          {symbol && <Link href={`/stocks/${symbol}`} className="mono">{symbol}</Link>}
          {name && <span className="dim" style={{ textTransform: "none", letterSpacing: 0 }}> {name}</span>}
          {r.report_date && <> · reported {day(r.report_date, { month: "short", day: "numeric" })}</>}
          {" "}· quarter ending {quarter}
        </header>
      )}
      {r.covers === false && (
        <p className="caption" style={{ margin: 0, color: "var(--warn)" }}>
          The prior quarter: the 10-Q for this report is not filed yet.
        </p>
      )}

      <div className={`read-takeaway ${frame}`}>
        <div style={{ fontWeight: 600 }}>Key takeaway</div>
        <div>{r.takeaway}</div>
      </div>

      <div className="read-tiles">
        <Tile label="Revenue" value={money(g.revenue)}
              chip={g.rev_qoq == null && g.rev_yoy == null ? null
                : `${pct(g.rev_qoq)} QoQ · ${pct(g.rev_yoy)} YoY`}
              tone={g.rev_yoy == null ? 0 : g.rev_yoy >= 20 ? 1 : g.rev_yoy <= -5 ? -1 : 0} />
        <Tile label="Gross margin" value={g.gm == null ? "—" : `${g.gm.toFixed(1)}%`}
              chip={g.gm_pp == null ? null : `${g.gm_pp > 0 ? "+" : ""}${g.gm_pp.toFixed(1)} pts QoQ`}
              tone={g.gm_pp == null ? 0 : g.gm_pp >= 1 ? 1 : g.gm_pp <= -1 ? -1 : 0} />
        <Tile label="Net income" value={money(g.net_income)}
              chip={g.net_income == null ? null : g.net_income > 0 ? "Positive" : "Loss"}
              tone={g.net_income == null ? 0 : g.net_income > 0 ? 1 : -1} />
        <Tile label="Free cash flow" value={money(g.fcf)} chip={fcfChip}
              tone={g.fcf == null ? 0 : g.fcf > 0 ? 1 : -1} />
      </div>

      <section className="stack" style={{ gap: "var(--gap-xs)" }}>
        <h3 className="read-h">What the numbers say</h3>
        <Lines lines={r.flags} />
      </section>

      <div className="row wrap" style={{ gap: "var(--gap-md)", alignItems: "flex-end" }}>
        <Bars title="Revenue by quarter" values={r.bars.map((b) => b.revenue)} />
        <Bars title="Free cash flow" values={r.bars.map((b) => b.fcf)} />
        <Bars title="Net income" values={r.bars.map((b) => b.net_income)} />
        <span className="caption dim">
          {g.dilution != null && <>shares {pct(g.dilution)} in a year</>}
          {g.dilution != null && g.net_cash != null && " · "}
          {g.net_cash != null && (g.net_cash >= 0
            ? <>net cash {money(g.net_cash)}</> : <>net debt {money(-g.net_cash)}</>)}
        </span>
      </div>

      {r.forensic.length > 0 && (
        <section className="stack" style={{ gap: "var(--gap-xs)" }}>
          <h3 className="read-h">What is not obvious</h3>
          <Lines lines={r.forensic} />
        </section>
      )}

      {deskParts.length > 0 && (
        <section className="stack" style={{ gap: 2 }}>
          <h3 className="read-h">The desk&rsquo;s own read</h3>
          <p className="footnote muted" style={{ margin: 0 }}>{deskParts.join(" · ")}</p>
        </section>
      )}

      <div className="read-final">
        <div style={{ fontWeight: 600 }}>Final read</div>
        <div>
          Growth: <strong className={r.verdict.growth === "REAL" ? "read-good"
            : r.verdict.growth === "WEAK" ? "read-bad" : "read-neutral"}>{r.verdict.growth}</strong>
          {" "}· Economic proof: <strong className={r.verdict.proof === "SHOWN" ? "read-good" : "read-bad"}>
            {r.verdict.proof}</strong>
        </div>
        <div className="footnote muted">Key question: {r.verdict.question}</div>
        <div className="footnote">{r.test}</div>
      </div>
    </article>
  );
}

/** On a stock's page, under "The business". */
export function QuarterlyPanel({ q }: { q: QuarterlyRead | null | undefined }) {
  if (!q) return null;
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="footnote muted">
        The latest quarter, read by fixed rules
        {q.report_date && <> · reported {day(q.report_date, { month: "short", day: "numeric" })}</>}
      </div>
      <EarningsReadCard r={q} heading={false} />
      <p className="caption dim" style={{ margin: 0 }}>
        From the company&rsquo;s 10-Q and 10-K filings, by Market Desk&rsquo;s rules.
        Every line, the takeaway and the final read are fixed rules on the
        filed numbers; nothing reads the press release, and none of it enters a
        screen or a rating. <Link href="/market/earnings">Every recent reporter</Link>.
      </p>
    </div>
  );
}
