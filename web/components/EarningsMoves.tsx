"use client";

import { Locked } from "@/components/Locked";
import { useGated } from "@/lib/useGated";
import type { EarningsMoves as Moves } from "@/lib/types";

/**
 * How far this stock has moved on its recent earnings reports.
 *
 * The question it answers is not whether the company will beat. It is how big a
 * gap a stop placed under a base has to survive if the stock is held through
 * the report. Measured close to close across the report — the last session
 * before the report day to the first after it — which catches the move whether
 * the company reported before the open or after the close.
 *
 * Free: the average size and how many reports it rests on. Subscribers: each
 * report, dated, and the largest.
 */
function pct(v: number, signed = false): string {
  const s = signed && v > 0 ? "+" : "";
  return `${s}${v.toFixed(1)}%`;
}

function date(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC",
  });
}

function Headline({ moves }: { moves: Moves }) {
  return (
    <p className="footnote" style={{ margin: 0 }}>
      On average <strong>{pct(moves.avg_abs_pct)}</strong> either way across its
      last {moves.count} report{moves.count === 1 ? "" : "s"}.
    </p>
  );
}

function Detail({ moves }: { moves: Moves }) {
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <Headline moves={moves} />
      {moves.largest && (
        <p className="caption dim" style={{ margin: 0 }}>
          Largest: {pct(moves.largest.move_pct, true)} on {date(moves.largest.date)}.
          {moves.up != null && ` Up after ${moves.up} of ${moves.count}.`}
        </p>
      )}
      {moves.reports && moves.reports.length > 0 && (
        <table className="data">
          <tbody>
            {moves.reports.map((r) => (
              <tr key={r.date}>
                <td>{date(r.date)}</td>
                <td className={r.move_pct >= 0 ? "gain" : "loss"}>
                  {pct(r.move_pct, true)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function GatedEarningsMoves({
  symbol, moves, locked,
}: {
  symbol: string;
  moves: Moves | null | undefined;
  locked: boolean;
}) {
  const fetched = useGated<Moves>(
    locked ? `stocks/earnings/${symbol.toLowerCase()}.json` : null,
  );

  if (!moves) {
    return (
      <p className="muted footnote" style={{ margin: 0 }}>
        No past reports on record for this company yet.
      </p>
    );
  }
  if (fetched.state === "ready" && fetched.data) return <Detail moves={fetched.data} />;
  if (!locked) return <Detail moves={moves} />;

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <Headline moves={moves} />
      {fetched.state === "loading" ? (
        <p className="caption dim" style={{ margin: 0 }}>Checking your subscription…</p>
      ) : (
        <Locked what={`Each of ${symbol}'s last ${moves.count} reports, dated, and the largest move,`}>
          {fetched.state === "error" && (
            <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
              The subscription check did not answer ({fetched.detail}).
            </p>
          )}
        </Locked>
      )}
      <p className="caption dim" style={{ margin: 0 }}>
        Close before the report day to close after it, so it holds whether the
        company reported before the open or after the close.
      </p>
    </div>
  );
}
