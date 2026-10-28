"use client";

import { Locked } from "@/components/Locked";
import { useGated } from "@/lib/useGated";
import type { HolderCounts, HolderDetail } from "@/lib/types";

/**
 * Which of the Market Desk's tracked funds hold this stock, from their latest
 * 13F filings against the quarter before.
 *
 * Forty-odd concentrated managers, not the whole market: the broad quant books
 * (Renaissance, Citadel and the like) hold a little of everything and are left
 * out of the count, so "held by six" means six funds that chose it. 13Fs are
 * filed up to 45 days after the quarter ends and show long stock only, so this
 * is where the money was, not where it is.
 *
 * Free: how many hold it and what they did last quarter. Subscribers: which
 * funds, and how much of each book it is.
 */
const CHANGE: Record<string, string> = {
  new: "new position", increased: "added", decreased: "trimmed",
  static: "unchanged", sold: "sold out",
};

function quarter(period: string | null | undefined): string {
  if (!period) return "";
  const [y, m] = period.split("-").map(Number);
  return `Q${Math.ceil(m / 3)} ${y}`;
}

function Headline({ c }: { c: HolderCounts }) {
  const moves = [
    c.new ? `${c.new} bought new` : "",
    c.added ? `${c.added} added` : "",
    c.trimmed ? `${c.trimmed} trimmed` : "",
    c.sold ? `${c.sold} sold out` : "",
  ].filter(Boolean);
  return (
    <div className="stack" style={{ gap: 2 }}>
      <p className="footnote" style={{ margin: 0 }}>
        {c.n > 0
          ? <>Held by <strong>{c.n}</strong> of {c.counted ?? "the"} tracked funds</>
          : <>No tracked fund holds it now</>}
        {c.period ? ` at the end of ${quarter(c.period)}` : ""}.
      </p>
      {moves.length > 0 && (
        <p className="caption dim" style={{ margin: 0 }}>Last quarter: {moves.join(", ")}.</p>
      )}
    </div>
  );
}

function Detail({ d }: { d: HolderDetail }) {
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <Headline c={d} />
      <table className="data">
        <thead>
          <tr><th>Fund</th><th>Last quarter</th><th>Of its book</th></tr>
        </thead>
        <tbody>
          {d.funds.map((f) => (
            <tr key={f.name}>
              <td className="text">{f.name}</td>
              <td className="text" style={{ textAlign: "right" }}>{CHANGE[f.change] ?? f.change}</td>
              <td>{f.change === "sold" ? "—" : `${f.pct.toFixed(1)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function GatedHolders({ symbol, counts, locked }: {
  symbol: string;
  counts: HolderCounts | null | undefined;
  locked: boolean;
}) {
  const fetched = useGated<HolderDetail>(
    locked ? `stocks/holders/${symbol.toLowerCase()}.json` : null,
  );

  if (!counts) {
    return (
      <p className="muted footnote" style={{ margin: 0 }}>
        None of the tracked funds held or sold it in their latest filings.
      </p>
    );
  }
  const note = (
    <p className="caption dim" style={{ margin: 0 }}>
      From 13F filings, which show long stock only and arrive up to 45 days
      after the quarter. The broad quant funds are left out.
    </p>
  );
  if (fetched.state === "ready" && fetched.data) {
    return <div className="stack" style={{ gap: "var(--gap-sm)" }}><Detail d={fetched.data} />{note}</div>;
  }
  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <Headline c={counts} />
      {locked && (fetched.state === "loading" ? (
        <p className="caption dim" style={{ margin: 0 }}>Checking your subscription…</p>
      ) : (
        <Locked what={`Which funds hold ${symbol}, what each did last quarter and how much of its book it is,`}>
          {fetched.state === "error" && (
            <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
              The subscription check did not answer ({fetched.detail}).
            </p>
          )}
        </Locked>
      ))}
      {note}
    </div>
  );
}
