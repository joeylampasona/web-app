import Link from "next/link";
import { TickerLink } from "./StockDrawer";

interface ScreenDiff {
  broke_out_today: string[];
  newly_forming: string[];
  left: { symbol: string; from: string; to: string | null; reason: string }[];
  total: number;
}

/**
 * What moved since the last run.
 *
 * The pipeline has computed this every night since it was written and nothing
 * ever showed it. It is the only reason to open the site on a Tuesday rather
 * than a Friday, so it goes above the list rather than below it.
 *
 * A quiet day says so. A day when nothing broke out is a reading about the
 * market, not a gap in the page, and hiding the panel on those days would make
 * the site look busier than the market was.
 */
export function WhatChanged({
  diff, screenName, href, direction = "long",
}: {
  diff: ScreenDiff | null | undefined;
  screenName: string;
  href?: string;
  /** "short" screens resolve downward, so they say so. */
  direction?: string;
}) {
  if (!diff) return null;
  // A breakdown screen describing its own movement as "broke out" was the site
  // saying the opposite of what happened.
  const verb = direction === "short" ? "broke down" : "broke out";
  const label = direction === "short" ? "Broke down" : "Broke out";

  const moved = diff.left.filter((row) => row.to);
  const gone = diff.left.filter((row) => !row.to);
  const quiet = !diff.broke_out_today.length && !diff.newly_forming.length
                && !diff.left.length;

  return (
    <section
      className="card stack"
      style={{ gap: "var(--gap-sm)", marginBottom: "var(--pad-lg)" }}
    >
      <div className="between">
        <span className="eyebrow" style={{ margin: 0 }}>Since the last run</span>
        {href && (
          <Link href={href} className="caption dim" style={{ textDecoration: "underline" }}>
            Did it work?
          </Link>
        )}
      </div>

      {quiet ? (
        <p className="footnote muted" style={{ margin: 0 }}>
          Nothing moved on {screenName} today — nothing {verb}, nothing new
          started forming, nothing dropped off. That is a reading about the market,
          not a fault.
        </p>
      ) : (
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          <Row label={label} symbols={diff.broke_out_today} />
          <Row label="Newly forming" symbols={diff.newly_forming} />
          <Row label="Moved on" symbols={moved.map((r) => r.symbol)}
               note={moved.length ? moved.map((r) => `${r.symbol} → ${r.to!.replace("_", " ")}`).join(", ") : undefined} />
          <Row label="Dropped off" symbols={gone.map((r) => r.symbol)}
               note={gone.length ? "no longer passes this screen's filters" : undefined} />
        </div>
      )}
    </section>
  );
}

function Row({ label, symbols, note }: { label: string; symbols: string[]; note?: string }) {
  if (!symbols.length) return null;
  return (
    <div>
      <div className="footnote muted">{label} · {symbols.length}</div>
      <div className="row wrap" style={{ gap: "var(--gap-xs)", marginTop: 2 }}>
        {symbols.map((symbol) => (
          <TickerLink key={symbol} symbol={symbol} className="badge mono">
            {symbol}
          </TickerLink>
        ))}
      </div>
      {note && <div className="caption dim" style={{ marginTop: 2 }}>{note}</div>}
    </div>
  );
}
