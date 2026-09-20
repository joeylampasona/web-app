import type { Forecast } from "@/lib/types";

/**
 * What analysts expect. Presented as a fact about analysts, not about the company.
 *
 * Everything else on this site is computed from prices it holds or copied from
 * a filing somebody signed. This is neither: a price target is a number a
 * person at a firm chose, and a consensus is an average of choices. So it is
 * attributed, counted and dated everywhere it appears — "57 analysts average
 * $800" is checkable and true, while "$800 is where this is going" is not
 * something anyone knows.
 *
 * The spread is shown as prominently as the average for the same reason. A
 * consensus of $800 with a range of $559 to $1,917 is a very different
 * statement from the same consensus with a range of $780 to $820, and printing
 * only the middle number hides which one you are looking at.
 */
export function ForecastPanel({ forecast }: { forecast: Forecast | null }) {
  if (!forecast) {
    return (
      <p className="muted footnote">
        No analyst coverage for this company. Most listed names have none, and
        an absence here is not a judgement about the business.
      </p>
    );
  }

  const { targets, upside_pct, eps, revenue, ratings, analysts } = forecast;
  const hasTarget = targets.mean !== null && targets.current !== null;

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      {hasTarget && (
        <>
          <div className="row wrap" style={{ gap: "var(--gap-lg)", alignItems: "baseline" }}>
            <span className="stack" style={{ gap: 0 }}>
              <span className="num" style={{ fontSize: "var(--size-h2)" }}>
                {money(targets.mean)}
              </span>
              <span className="caption dim">
                average target{analysts ? ` · ${analysts} analysts` : ""}
              </span>
            </span>
            {upside_pct !== null && (
              <span className="stack" style={{ gap: 0 }}>
                <span
                  className="num"
                  style={{
                    fontSize: "var(--size-h3)",
                    color: upside_pct >= 0 ? "var(--gain)" : "var(--loss)",
                  }}
                >
                  {upside_pct >= 0 ? "▲" : "▼"} {upside_pct >= 0 ? "+" : ""}
                  {upside_pct.toFixed(1)}%
                </span>
                <span className="caption dim">against {money(targets.current)}</span>
              </span>
            )}
          </div>

          <Spread targets={targets} />
        </>
      )}

      {ratings && <Ratings ratings={ratings} />}

      {eps.length > 0 && (
        <Estimates title="Earnings per share" rows={eps} format={(v) => money(v, 2)} />
      )}
      {revenue.length > 0 && (
        <Estimates title="Revenue" rows={revenue} format={big} />
      )}

      <p className="caption dim" style={{ margin: 0 }}>
        These are analysts&rsquo; estimates, not ours, and not a projection this
        site endorses. They are published here because what the sell side
        expects is itself a fact about the market
        {forecast.fetched_at ? `, read ${age(forecast.fetched_at)}` : ""}.
      </p>
    </div>
  );
}

/** The range, drawn. Where the current price sits inside it is the reading. */
function Spread({ targets }: { targets: Forecast["targets"] }) {
  const { low, high, mean, current } = targets;
  if (low === null || high === null || high <= low) return null;
  const place = (v: number | null) =>
    v === null ? null : Math.min(Math.max((v - low) / (high - low), 0), 1) * 100;
  const meanAt = place(mean);
  const nowAt = place(current);

  return (
    <div className="stack" style={{ gap: "var(--gap-xs)" }}>
      <div style={{ position: "relative", height: 22 }}>
        <div style={{
          position: "absolute", top: 9, left: 0, right: 0, height: 4,
          borderRadius: "var(--radius-pill)", background: "var(--border-stronger)",
        }} />
        {meanAt !== null && (
          <div title="Average target" style={{
            position: "absolute", top: 5, left: `${meanAt}%`, width: 2, height: 12,
            background: "var(--text-secondary)", transform: "translateX(-1px)",
          }} />
        )}
        {nowAt !== null && (
          <div title="Current price" style={{
            position: "absolute", top: 4, left: `${nowAt}%`, width: 10, height: 10,
            borderRadius: "50%", background: "var(--brand)",
            border: "2px solid var(--surface-1)", transform: "translateX(-5px)",
          }} />
        )}
      </div>
      <div className="between caption dim">
        <span className="num">{money(low)} low</span>
        <span className="num">{money(high)} high</span>
      </div>
    </div>
  );
}

function Ratings({ ratings }: { ratings: NonNullable<Forecast["ratings"]> }) {
  const rows: [string, number, string][] = [
    ["Strong buy", ratings.strongBuy, "var(--gain)"],
    ["Buy", ratings.buy, "var(--gain)"],
    ["Hold", ratings.hold, "var(--text-muted)"],
    ["Sell", ratings.sell, "var(--loss)"],
    ["Strong sell", ratings.strongSell, "var(--loss)"],
  ];
  const total = rows.reduce((sum, [, n]) => sum + n, 0) || 1;
  return (
    <div className="stack" style={{ gap: 3 }}>
      {rows.map(([label, count, colour]) => (
        <div key={label} className="row caption"
             style={{ gap: "var(--gap-sm)", alignItems: "center" }}>
          <span className="dim" style={{ minWidth: 76 }}>{label}</span>
          <span aria-hidden style={{
            flexGrow: 1, height: 5, borderRadius: "var(--radius-pill)",
            background: "var(--border-stronger)", overflow: "hidden",
          }}>
            <span style={{
              display: "block", height: "100%", width: `${(count / total) * 100}%`,
              background: colour, opacity: 0.85,
            }} />
          </span>
          <span className="num" style={{ minWidth: 20, textAlign: "right" }}>{count}</span>
        </div>
      ))}
    </div>
  );
}

function Estimates({ title, rows, format }: {
  title: string;
  rows: Forecast["eps"];
  format: (v: number | null) => string;
}) {
  return (
    <div className="stack" style={{ gap: "var(--gap-xs)" }}>
      <div className="caption dim">{title}</div>
      <div className="scroll-x">
        <table className="data">
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Period</th>
              <th>Estimate</th><th>Low</th><th>High</th><th>Analysts</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.period}>
                <td className="text caption">{row.label}</td>
                <td className="num">{format(row.avg)}</td>
                <td className="num caption dim">{format(row.low)}</td>
                <td className="num caption dim">{format(row.high)}</td>
                <td className="num caption dim">
                  {row.analysts === null ? "—" : row.analysts.toFixed(0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function money(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `$${value.toFixed(digits)}`;
}

function big(value: number | null): string {
  if (value === null || value === undefined) return "—";
  const n = Math.abs(value);
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toFixed(0)}`;
}

/** Age in plain words. A target read last Tuesday is not today's view. */
function age(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "recently";
  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days} days ago`;
}
