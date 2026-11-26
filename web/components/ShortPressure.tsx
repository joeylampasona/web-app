import Link from "next/link";
import type { ShortInterest, SqueezeFile, SqueezeRead } from "@/lib/types";
import { shortDay } from "./CarriedOver";

/**
 * Short selling, as the Market Desk carried it: FINRA's daily short volume
 * for the names its brief ranked, and FINRA's twice-monthly short interest.
 *
 * Two different figures and the page keeps them apart. Short volume is the
 * share of one session's trading that was marked short, and it counts market
 * makers hedging, so half of all volume being "short" is ordinary. Short
 * interest is how many shares were actually held short on a settlement date,
 * published about nine business days later. Neither is a signal here. The
 * desk's own contract calls the squeeze read context only, and so does this.
 */
function share(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

function shares(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}bn`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}m`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return v.toLocaleString("en-US");
}

function changed(v: number | null | undefined): string {
  return v == null ? "" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

/** One name's short interest, in a sentence. */
export function ShortInterestLine({ held }: { held: ShortInterest }) {
  const when = shortDay(held.settlement);
  return (
    <>
      <strong className="num">{shares(held.shares)}</strong> shares short
      {held.chg_pct != null && (
        <>, <span className="num">{changed(held.chg_pct)}</span> against the settlement before</>
      )}
      {held.days_to_cover != null && (
        <>, <span className="num">{held.days_to_cover.toFixed(1)}</span> days of average volume to cover</>
      )}
      {when && <>, as of {when}</>}.
    </>
  );
}

/** The block on a stock's own page. Nothing when the desk did not look. */
export function ShortInterestBlock({ held, squeeze }: {
  held: ShortInterest | null | undefined;
  squeeze: SqueezeRead | null | undefined;
}) {
  const hasHeld = Boolean(held && held.shares);
  const hasVolume = Boolean(squeeze && squeeze.short_ratio != null);
  if (!hasHeld && !hasVolume) return null;
  const why = (squeeze?.why ?? []).filter(Boolean);
  return (
    <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
      <div className="label-caps" style={{ color: "var(--text-muted)" }}>Short selling</div>
      {hasHeld && held && (
        <p className="footnote" style={{ margin: 0 }}>
          <ShortInterestLine held={held} />
        </p>
      )}
      {hasVolume && squeeze && (
        <p className="footnote" style={{ margin: 0 }}>
          <strong className="num">{share(squeeze.short_ratio)}</strong> of the last
          session&apos;s volume was marked short
          {squeeze.short_ratio_20d != null && (
            <>, against <span className="num">{share(squeeze.short_ratio_20d)}</span> over twenty sessions</>
          )}.
          {squeeze.met != null && (
            <> The desk&apos;s squeeze conditions: {squeeze.met} of 3 met
              {why.length > 0 ? ` (${why.join("; ")})` : ""}.</>
          )}
        </p>
      )}
      <p className="caption dim" style={{ margin: 0 }}>
        FINRA, via the Market Desk. Short interest is published twice a month,
        about nine business days after settlement. Short volume counts market
        makers hedging, so a high share is ordinary on its own. Context, not a
        signal.
      </p>
    </div>
  );
}

/** The market page's table: the names the desk ranked that night. */
export function ShortPressure({ file }: { file: SqueezeFile | null }) {
  if (!file || !file.rows || file.rows.length === 0) return null;
  const rows = file.rows;
  const settled = [...new Set(rows.map((r) => r.short_interest?.settlement).filter(Boolean))];
  return (
    <section className="stack" id="short-pressure"
             style={{ gap: "var(--gap-sm)", marginTop: "var(--pad-xl)" }}>
      <div className="eyebrow">Short pressure</div>
      <p className="muted footnote" style={{ margin: 0, maxWidth: "78ch" }}>
        The {rows.length} names the Market Desk ranked for short pressure on its
        last run: how much of the latest session&apos;s volume was marked short
        against the twenty sessions before, and how many shares were held short
        at the last settlement. A short list, not a screen of the market.
      </p>
      <div className="scroll-x card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th className="text">Ticker</th>
              <th>Short volume</th>
              <th>20-day</th>
              <th>Sessions</th>
              <th className="text">Conditions met</th>
              <th>Shares short</th>
              <th>Change</th>
              <th>Days to cover</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const why = (row.why ?? []).filter(Boolean);
              const held = row.short_interest;
              const above = row.short_ratio != null && row.short_ratio_20d != null
                && row.short_ratio > row.short_ratio_20d;
              return (
                <tr key={row.symbol}>
                  <td className="text">
                    {row.in_universe ? (
                      <Link href={`/stocks/${row.symbol}`} className="mono" style={{ fontWeight: 600 }}>
                        {row.symbol}
                      </Link>
                    ) : (
                      <span className="mono" style={{ fontWeight: 600 }}
                            title="Outside the names this site follows">{row.symbol}</span>
                    )}
                    {row.name && row.name !== row.symbol && (
                      <div className="caption dim">{row.name}</div>
                    )}
                  </td>
                  <td className="num" style={{ fontWeight: above ? 600 : 400 }}>{share(row.short_ratio)}</td>
                  <td className="num dim">{share(row.short_ratio_20d)}</td>
                  <td className="num dim">{row.short_days ?? "—"}</td>
                  <td className="text" style={{ minWidth: 190 }}>
                    <span className="num" style={{ fontWeight: row.watch ? 600 : 400 }}>
                      {row.met ?? 0} of 3
                    </span>
                    {why.length > 0 && <span className="caption dim"> · {why.join("; ")}</span>}
                  </td>
                  <td className="num">{held ? shares(held.shares) : "—"}</td>
                  <td className={`num ${held?.chg_pct == null ? "dim" : ""}`}>
                    {held?.chg_pct == null ? "—" : changed(held.chg_pct)}
                  </td>
                  <td className="num">
                    {held?.days_to_cover == null ? "—" : held.days_to_cover.toFixed(1)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>
        Context, not a signal. FINRA&apos;s short volume counts market makers
        hedging as well as anyone betting against the stock, so around half of
        all volume is ordinarily marked short. Sessions is how many days of
        short-volume history the comparison rests on.
        {settled.length === 1 && shortDay(settled[0]) && (
          <> Short interest is as of the {shortDay(settled[0])} settlement; FINRA
            publishes it twice a month, and the change is against the settlement
            before.</>
        )}
        {" "}Names in plain type are outside the universe this site follows.
        Source: FINRA, via the Market Desk.
      </p>
    </section>
  );
}
