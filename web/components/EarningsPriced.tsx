import type { EarningsMoves, EarningsPriced as Priced, EarningsPricedLast } from "@/lib/types";

/**
 * What the options market expects from the next report, beside what the stock
 * has actually done on its last ones.
 *
 * The priced move is the at-the-money straddle at the first expiry after the
 * report, as a share of the price: roughly what it costs to bet on a move
 * either way. It comes from the Market Desk's chain read, which covers the
 * week's most traded reporters. The usual move is this site's own measurement
 * (close before the report to close after), so the two are compared like for
 * like. Neither is a forecast of direction.
 */
function pct(v: number): string {
  return `${v.toFixed(1)}%`;
}

function signed(v: number): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function day(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", timeZone: "UTC",
  });
}

const HOUR: Record<string, string> = { bmo: "before the open", amc: "after the close" };

export function EarningsPriced({ next, last, usual }: {
  next: Priced | null | undefined;
  last: EarningsPricedLast | null | undefined;
  usual: EarningsMoves | null | undefined;
}) {
  if (!next && !(last && last.realised_pct != null)) return null;
  const ratio = next && usual?.avg_abs_pct ? next.implied_pct / usual.avg_abs_pct : null;

  return (
    <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
      {next && (
        <>
          <p className="footnote" style={{ margin: 0 }}>
            Options price a <strong>±{pct(next.implied_pct)}</strong> move for the{" "}
            {day(next.report_date)} report{HOUR[next.hour] ? ` (${HOUR[next.hour]})` : ""}.
          </p>
          {ratio != null && usual && (
            <p className="caption dim" style={{ margin: 0 }}>
              That is {ratio.toFixed(1)}× its usual {pct(usual.avg_abs_pct)} across{" "}
              {usual.count} report{usual.count === 1 ? "" : "s"}
              {ratio >= 1.5 ? ": priced richer than it has tended to move."
                : ratio <= 0.75 ? ": priced for less than it has tended to move."
                  : "."}
            </p>
          )}
        </>
      )}
      {last && last.realised_pct != null && (
        <p className="caption dim" style={{ margin: 0 }}>
          Last report ({day(last.report_date)}): priced ±{pct(last.implied_pct)}, moved{" "}
          <span className={last.realised_pct >= 0 ? "gain" : "loss"}>
            {signed(last.realised_pct)}
          </span>
          {last.inside == null ? "." : last.inside ? ", inside the priced move." : ", beyond it."}
        </p>
      )}
      <p className="caption dim" style={{ margin: 0 }}>
        From the at-the-money straddle at the first expiry after the report.
        Says how big, never which way.
      </p>
    </div>
  );
}
