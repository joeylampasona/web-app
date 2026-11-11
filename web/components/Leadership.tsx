import Link from "next/link";
import { AlignChip, pct } from "./Radar";
import type {
  LayerCounts, LeadershipLayer, LeadershipReading, LeadershipSummary,
} from "@/lib/types";

/**
 * Leadership layers: every stock against its own industry, and the industry
 * against the S&P 500.
 *
 * A stock's industry is an equal-weighted index of the industry's members,
 * so "ahead" means ahead of the average company in the same line of business.
 * The industry's own trend is the radar's: its ratio to the S&P 500 fully,
 * partly or not aligned, and ahead or behind over six months. Seven layers,
 * first rule that holds. A layer says where a stock sits, not what to do
 * with it, and no screen or rating uses it.
 */
export const LAYER_HELP: Record<LeadershipLayer, string> = {
  front: "Ahead of its industry over one, three and six months, in an industry fully aligned and ahead of the S&P 500.",
  specific: "Ahead of its industry over all three, in an industry that is behind the S&P 500 over six months: strength the group does not share.",
  developing: "Ahead of its industry over one and three months and not behind over six, in an industry at least partly aligned.",
  weak_in_strong: "Behind its industry over one and six months while the industry is fully aligned and ahead of the S&P 500.",
  turning: "Behind its industry over six months, but ahead over one and three.",
  caution: "Behind its industry over all three, in an industry that is not ahead of the S&P 500.",
  unconfirmed: "None of the patterns above holds.",
};

/** The pipeline's own names for the layers, for rows that carry only the key. */
export const LAYER_LABELS: Record<LeadershipLayer, string> = {
  front: "Front line", specific: "Stock-specific strength", developing: "Developing",
  weak_in_strong: "Strong industry, weak stock", turning: "Turning", caution: "Caution",
  unconfirmed: "Unconfirmed",
};

const TONE: Partial<Record<LeadershipLayer, string>> = {
  front: "badge badge--gain", specific: "badge badge--brand", developing: "badge badge--gain",
  turning: "badge", weak_in_strong: "badge badge--warn", caution: "badge badge--loss",
};

export function LayerChip({ layer, label }: { layer: LeadershipLayer; label: string }) {
  return <span className={TONE[layer] ?? "badge"} title={LAYER_HELP[layer]}>{label}</span>;
}

function delta(now: number, then: number | undefined): string | null {
  if (then === undefined) return null;
  const d = now - then;
  return d === 0 ? "unchanged" : `${d > 0 ? "+" : ""}${d}`;
}

function day(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", timeZone: "UTC",
  });
}

/** One stock's layer, for its page. */
export function StockLeadership({ r }: { r: LeadershipReading | null | undefined }) {
  if (!r) {
    return (
      <p className="muted footnote" style={{ margin: 0 }}>
        Not read: under $3, or no price on the last session.
      </p>
    );
  }
  const g = r.group;
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        <LayerChip layer={r.layer} label={r.label} />
        <span className="caption dim">{LAYER_HELP[r.layer]}</span>
      </div>
      <div className="grid-3">
        {([["One month", r.rs21], ["Three months", r.rs63], ["Six months", r.rs126]] as const)
          .map(([label, v]) => (
            <div key={label} className="card" style={{ padding: "var(--pad-sm) var(--pad-md)" }}>
              <div className="caption muted">{label} against {r.vs_slug ? "its industry" : "the S&P 500"}</div>
              <div className="num" style={{ fontSize: "var(--size-h3)",
                                           color: v == null ? undefined : v > 0 ? "var(--gain)" : v < 0 ? "var(--loss)" : undefined }}>
                {pct(v)}
              </div>
            </div>
          ))}
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        {r.vs_slug ? (
          <>
            Read against an equal-weighted index of{" "}
            <Link href={`/industries/${r.vs_slug}`}>{r.vs}</Link>, which is{" "}
            {g?.rs126 == null ? "unmeasured" : `${pct(g.rs126)}`} against the S&amp;P 500
            over six months <AlignChip state={g?.aligned} />.
          </>
        ) : (
          <>
            Its industry has too few members to make an index of, so it is read
            against the S&amp;P 500 and can only be turning, caution or unconfirmed.
          </>
        )}
      </p>
    </div>
  );
}

/** Counts per layer with the change on the day and on the week. */
export function LayerCountsGrid({ s }: { s: LeadershipSummary }) {
  const now = s.counts;
  if (!now) return null;
  return (
    <div className="grid-auto">
      {s.order.map((k) => {
        const day1 = delta(now[k], s.yesterday?.[k]);
        const week = delta(now[k], s.week_ago?.[k]);
        return (
          <div key={k} className="card stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="footnote muted">{s.labels[k]}</div>
            <div className="num" style={{ fontSize: "var(--size-h2)" }}>{now[k].toLocaleString("en-US")}</div>
            <div className="caption dim">
              {day1 && <>{day1} on the day</>}
              {day1 && week && " · "}
              {week && <>{week} on the week</>}
            </div>
            <p className="caption dim" style={{ margin: 0 }}>{LAYER_HELP[k]}</p>
          </div>
        );
      })}
    </div>
  );
}

export function LayerPath({ path, order, labels }: {
  path: LayerCounts[]; order: LeadershipLayer[]; labels: Record<LeadershipLayer, string>;
}) {
  if (path.length < 2) return null;
  return (
    <div className="scroll-x card" style={{ padding: 0 }}>
      <table className="data">
        <thead>
          <tr>
            <th className="text">Session</th>
            {order.map((k) => <th key={k}>{labels[k]}</th>)}
          </tr>
        </thead>
        <tbody>
          {path.map((row) => (
            <tr key={row.date}>
              <td className="text">{day(row.date)}</td>
              {order.map((k) => <td key={k} className="num">{row[k]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LayerLists({ s }: { s: LeadershipSummary }) {
  const shown = s.order.filter((k) => (s.top[k] ?? []).length > 0);
  return (
    <div className="grid-auto">
      {shown.map((k) => (
        <div key={k} className="card stack" style={{ gap: "var(--gap-xs)" }}>
          <div className="footnote muted">{s.labels[k]}</div>
          {(s.top[k] ?? []).map((r) => (
            <div key={r.symbol} className="between caption">
              <span>
                <Link href={`/stocks/${r.symbol}`} className="mono">{r.symbol}</Link>{" "}
                <span className="dim">{r.vs}</span>
              </span>
              <span className="num">
                {pct(k === "turning" ? r.rs63 : r.rs126, 0)}
                <span className="dim"> {k === "turning" ? "3m" : "6m"}</span>
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export function LayerIndustries({ s }: { s: LeadershipSummary }) {
  if (!s.industries.length) return null;
  return (
    <div className="scroll-x card" style={{ padding: 0 }}>
      <table className="data">
        <thead>
          <tr>
            <th className="text">Industry</th><th>Names</th><th>Front line</th>
            <th>Developing</th><th>Weak in strong</th><th>Caution</th>
            <th>6m vs S&amp;P 500</th><th className="text">Trend</th>
          </tr>
        </thead>
        <tbody>
          {s.industries.map((g) => (
            <tr key={g.slug}>
              <td className="text"><Link href={`/industries/${g.slug}`}>{g.name}</Link></td>
              <td className="num">{g.n}</td>
              <td className="num">{g.front}</td>
              <td className="num">{g.developing}</td>
              <td className="num">{g.weak_in_strong}</td>
              <td className="num">{g.caution}</td>
              <td className="num">{pct(g.rs126)}</td>
              <td className="text"><AlignChip state={g.aligned} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Every stock as one proportional bar, a segment per layer.
 *
 * The cards of counts could not show the one thing that matters about them:
 * how small the front line is against the whole. One bar can, and the key
 * under it carries each count and its change since a week ago.
 */
export function LayerBar({ s, names = 6 }: { s: LeadershipSummary; names?: number }) {
  const now = s.counts;
  if (!now) return null;
  const front = (s.top.front ?? []).slice(0, names);
  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <div className="layerbar" role="img"
           aria-label={`Leadership layers as shares of ${now.n.toLocaleString("en-US")} stocks: `
             + s.order.map((k) => `${s.labels[k]} ${now[k]}`).join(", ")}>
        {s.order.map((k) => now[k] > 0 && (
          <span key={k} className={`layer--${k}`} style={{ flex: `${now[k]} 1 0` }}
                title={`${s.labels[k]}: ${now[k].toLocaleString("en-US")}`} />
        ))}
      </div>
      <div className="layer-key">
        {s.order.map((k) => {
          const week = delta(now[k], s.week_ago?.[k]);
          return (
            <div key={k} className="row" style={{ gap: "var(--gap-sm)", alignItems: "flex-start" }}
                 title={LAYER_HELP[k]}>
              <span aria-hidden className={`sw layer--${k}`} />
              <div className="stack" style={{ gap: 0 }}>
                <span className="label-caps" style={{ textTransform: "none" }}>{s.labels[k]}</span>
                <span className="num">
                  <span style={{ fontWeight: 600 }}>{now[k].toLocaleString("en-US")}</span>
                  {week && <span className="caption dim"> ({week})</span>}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      {front.length > 0 && (
        <div className="row wrap footnote" style={{ gap: "4px var(--gap-lg)" }}>
          <span className="label-caps hl" style={{ padding: "2px 8px" }}>Front line, strongest first</span>
          {front.map((r) => (
            <Link key={r.symbol} href={`/stocks/${r.symbol}`} className="mono"
                  style={{ fontWeight: 600, display: "inline-flex", alignItems: "center",
                           minHeight: "var(--h-control)" }}>
              {r.symbol}
            </Link>
          ))}
          <Link href="/market/leadership" style={{ textDecoration: "underline" }}>
            all {now.front}
          </Link>
        </div>
      )}
    </div>
  );
}
