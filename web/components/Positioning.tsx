"use client";

import { Locked } from "@/components/Locked";
import { Sparkline } from "@/components/Sparkline";
import { useGated } from "@/lib/useGated";
import type { PositioningFile, PositioningMarket } from "@/lib/types";

/**
 * CFTC Commitments of Traders: how the fast money is positioned in eight
 * futures markets, and how stretched that is against its own history.
 *
 * The number that matters is the percentile, not the net. Leveraged funds are
 * structurally short S&P futures most of the time — they hedge long stock
 * books with them — so "net short" alone says nothing; "net short, and more so
 * than in any week of the last year" says a great deal. The extremes are where
 * this table has something to say: crowded positions are the ones that unwind
 * fastest when the market moves against them.
 *
 * Free: the S&P 500 and Nasdaq rows. Subscribers: all eight, because the
 * reading is the comparison across markets.
 */
function k(v: number | null): string {
  if (v == null) return "—";
  const s = v > 0 ? "+" : v < 0 ? "−" : "";
  const a = Math.abs(v);
  return a >= 10_000 ? `${s}${Math.round(a / 1000).toLocaleString("en-US")}k`
                     : `${s}${a.toLocaleString("en-US")}`;
}

function ordinal(n: number): string {
  const r = n % 100;
  if (r >= 11 && r <= 13) return `${n}th`;
  return `${n}${({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
}

function Percentile({ value }: { value: number | null }) {
  if (value == null) return <span className="dim">—</span>;
  const edge = value <= 10 || value >= 90;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span aria-hidden style={{
        width: 48, height: 6, borderRadius: 3, background: "var(--border)",
        position: "relative", display: "inline-block",
      }}>
        <span style={{
          position: "absolute", left: `calc(${value}% - 3px)`, top: -1, width: 6, height: 8,
          borderRadius: 2, background: edge ? "var(--warn)" : "var(--text-secondary)",
        }} />
      </span>
      <span style={{ color: edge ? "var(--warn)" : undefined }}>{ordinal(value)}</span>
    </span>
  );
}

function Table({ markets }: { markets: PositioningMarket[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="data">
        <thead>
          <tr>
            <th>Market</th>
            <th>Net</th>
            <th>Week</th>
            <th>vs last year</th>
            <th>vs 3 years</th>
            <th>52 weeks</th>
          </tr>
        </thead>
        <tbody>
          {markets.map((m) => (
            <tr key={m.key}>
              <td className="text">
                <div>{m.label}</div>
                <div className="caption dim">
                  {m.group}
                  {m.extreme && <> · <span style={{ color: "var(--warn)" }}>{m.extreme}</span></>}
                </div>
              </td>
              <td>
                <div>{k(m.net)}</div>
                {m.net_oi != null && (
                  <div className="caption dim">{m.net_oi > 0 ? "+" : m.net_oi < 0 ? "−" : ""}{Math.abs(m.net_oi)}% of OI</div>
                )}
              </td>
              <td className={m.chg == null ? "" : m.chg >= 0 ? "gain" : "loss"}>{k(m.chg)}</td>
              <td><Percentile value={m.pct52} /></td>
              <td><Percentile value={m.pct156} /></td>
              <td>
                <Sparkline points={m.history.map(([, net]) => net)} width={80} height={22} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function GatedPositioning({ file }: { file: PositioningFile }) {
  const gated = Boolean(file.gated);
  const full = useGated<PositioningFile>(gated ? "market/positioning.json" : null);

  if (!gated) return <Table markets={file.markets} />;
  if (full.state === "ready" && full.data?.markets?.length) {
    return <Table markets={full.data.markets} />;
  }
  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <Table markets={file.markets} />
      {full.state === "loading" ? (
        <p className="caption dim" style={{ margin: 0 }}>Checking your subscription…</p>
      ) : (
        <Locked what="Small caps, VIX, Treasuries, the dollar, gold and oil,"
                shown={file.markets.length} total={file.count ?? file.markets.length}>
          {full.state === "error" && (
            <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
              The subscription check did not answer ({full.detail}).
            </p>
          )}
        </Locked>
      )}
    </div>
  );
}
