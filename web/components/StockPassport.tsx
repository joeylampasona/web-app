"use client";

import Link from "next/link";
import { compactMoney, isRanked, price } from "@/lib/format";
import { useQuote } from "@/lib/useQuotes";
import type { StockFile } from "@/lib/types";
import { QuadrantBadge, StageBadge } from "./Badges";
import { LAYER_HELP, LayerChip } from "./Leadership";
import { PriceChange } from "./PriceChange";
import { RsRing } from "./RsRing";
import { WatchStar } from "./WatchStar";

/**
 * The passport: one band that says where a stock stands, before the chart.
 *
 * The page used to open with a name and scatter the rest down two columns:
 * the rating in a corner, the layer four sections down, the next report in a
 * timeline, the last quarter near the bottom. These six readings are the ones
 * a reader checks first, so they sit together, each a cell with its label, its
 * figure and one line of context, and each links to the section that has the
 * detail.
 *
 * Nothing here is new data. Every cell repeats a reading the page already
 * carries further down, and a cell with nothing to say says so rather than
 * disappearing, so the band is the same shape on every stock.
 */
function day(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", timeZone: "UTC",
  });
}

function pct(v: number | null | undefined, digits = 1): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;
}

function Cell({ label, href, children }: {
  label: string; href?: string; children: React.ReactNode;
}) {
  return (
    <div className="passport-cell">
      <div className="label-caps" style={{ color: "var(--text-muted)" }}>
        {href ? <a href={href}>{label}</a> : label}
      </div>
      {children}
    </div>
  );
}

export function StockPassport({ stock }: { stock: StockFile }) {
  const quote = useQuote(stock.symbol);
  const last = stock.bars.at(-1)?.close ?? null;
  const prior = stock.bars.at(-2)?.close ?? null;
  const live = Boolean(quote && quote.last > 0);
  const shown = live ? quote!.last : last;
  const change = live ? quote!.change_pct
    : last != null && prior ? ((last / prior) - 1) * 100 : null;

  const range = stock.range_52w;
  const span = range ? range.high - range.low : 0;
  const at = range && span > 0 && shown != null
    ? Math.min(100, Math.max(0, ((shown - range.low) / span) * 100)) : null;
  const fromHigh = range && shown != null && range.high > 0
    ? (shown / range.high - 1) * 100 : null;

  const setup = stock.primary_setup;
  const layer = stock.leadership;
  const report = stock.catalyst_roadmap.find(
    (e) => e.type === "earnings" && !e.readthrough && e.days_until >= 0);
  const quarter = stock.fundamentals?.quarterly ?? null;
  const ranked = isRanked(stock.rs_rating);
  const drift = stock.rs_change_m1;

  return (
    <header className="passport">
      <div className="passport-top">
        <div className="stack" style={{ gap: "var(--gap-sm)", minWidth: 0 }}>
          <div className="kicker">
            <span className="mono" style={{ color: "var(--text-primary)", fontWeight: 600 }}>
              {stock.symbol}
            </span>
            {" · "}
            {stock.industry_slug
              ? <Link href={`/industries/${stock.industry_slug}`}>{stock.industry}</Link>
              : stock.industry}
            {" · "}{compactMoney(stock.market_cap)}
            {stock.market_cap_basis === "share_class" && stock.market_cap != null && (
              <span title="Built from one share class's count. Other classes are not included, so the company may be worth more.">
                {" "}(one share class)
              </span>
            )}
          </div>
          <h1 className="passport-name">{stock.name}</h1>
          {stock.themes.length > 0 && (
            <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
              {stock.themes.map((slug) => (
                <Link key={slug} href={`/themes/${slug}`} className="badge">{slug}</Link>
              ))}
            </div>
          )}
        </div>
        <div className="passport-price">
          {shown != null && (
            <div className="stack" style={{ gap: 2, alignItems: "flex-end" }}>
              <div className="row" style={{ gap: "var(--gap-sm)", alignItems: "baseline" }}>
                <span className="num passport-figure">{price(shown)}</span>
                <PriceChange value={change} />
              </div>
              <span className="caption dim">{live ? "Delayed quote" : "Last close"}</span>
            </div>
          )}
          {/* Always here: a stock on no screen has no card to carry it. */}
          <WatchStar symbol={stock.symbol} withLabel />
        </div>
      </div>

      <div className="passport-grid">
        <Cell label="Relative strength">
          <div className="row" style={{ gap: "var(--gap-md)", alignItems: "center" }}>
            <RsRing rating={stock.rs_rating} />
            <div className="stack" style={{ gap: 2, minWidth: 0 }}>
              <span className="caption" style={{ color: "var(--text-secondary)" }}>
                {ranked ? "of 99, against every stock" : "Not ranked yet"}
              </span>
              {drift != null && (
                <span className="num caption" style={{
                  color: drift > 0 ? "var(--gain)" : drift < 0 ? "var(--loss)" : undefined }}>
                  {drift > 0 ? "▲" : drift < 0 ? "▼" : "•"} {drift > 0 ? "+" : ""}{drift} on the month
                </span>
              )}
            </div>
          </div>
          <div><QuadrantBadge quadrant={stock.quadrant} /></div>
        </Cell>

        <Cell label="Against its industry" href="#industry">
          {layer ? (
            <>
              <div><LayerChip layer={layer.layer} label={layer.label} /></div>
              <div className="num passport-value" style={{
                color: layer.rs126 == null ? undefined
                  : layer.rs126 > 0 ? "var(--gain)" : layer.rs126 < 0 ? "var(--loss)" : undefined }}>
                {pct(layer.rs126)}
              </div>
              <div className="caption dim" title={LAYER_HELP[layer.layer]}>
                six months against {layer.vs_slug ? layer.vs : "the S&P 500"}
              </div>
            </>
          ) : (
            <div className="caption dim">Not read: under $3, or no price on the last session.</div>
          )}
        </Cell>

        <Cell label={range && range.sessions < 250 ? `${range.sessions}-session range` : "52-week range"}>
          {range && at != null ? (
            <>
              <div className="num passport-value">
                {fromHigh == null ? "—" : fromHigh > -0.05 ? "At the high" : `${pct(fromHigh)}`}
              </div>
              <div className="caption dim">{fromHigh != null && fromHigh <= -0.05 ? "from the high" : " "}</div>
              <div className="range-bar" role="img" style={{ marginTop: 6 }}
                   aria-label={`${Math.round(at)}% of the way from the low of ${price(range.low)} to the high of ${price(range.high)}`}>
                <span className="range-fill" style={{ width: `${at}%` }} />
                <span className="range-mark" style={{ left: `${at}%` }} />
              </div>
              <div className="between caption dim num">
                <span>{price(range.low)}</span><span>{price(range.high)}</span>
              </div>
            </>
          ) : (
            <div className="caption dim">Too little history for a range.</div>
          )}
        </Cell>

        <Cell label="Setup">
          {setup ? (
            <>
              <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
                <Link href={`/screens/${setup.screen}`} className="badge badge--brand"
                      style={{ textTransform: "capitalize" }}>
                  {setup.screen.replace(/_/g, " ")}
                </Link>
                <StageBadge stage={setup.stage} />
              </div>
              <div className="num passport-value" style={{
                color: setup.now_vs_pivot_pct == null ? undefined
                  : setup.now_vs_pivot_pct >= 0 ? "var(--gain)" : "var(--loss)" }}>
                {pct(setup.now_vs_pivot_pct)}
              </div>
              <div className="caption dim">against the pivot at {price(setup.pivot)}</div>
            </>
          ) : (
            <>
              <div className="passport-value" style={{ fontFamily: "var(--font-display)" }}>On no screen</div>
              <div className="caption dim">
                No base, flag or squeeze in place tonight. <a href="#structure" style={{ textDecoration: "underline" }}>What is and is not there</a>
              </div>
            </>
          )}
        </Cell>

        <Cell label="Next report" href="#roadmap">
          {report ? (
            <>
              <div className="num passport-value">
                {report.days_until === 0 ? "Today" : report.days_until === 1 ? "Tomorrow"
                  : `${report.days_until} days`}
              </div>
              <div className="caption dim">
                {day(report.date)} · {report.confirmed === "confirmed" ? "confirmed" : "not confirmed"}
              </div>
              {report.priced_move_pct ? (
                <div className="caption">
                  options price <span className="num hl" style={{ fontWeight: 600 }}>
                    ±{report.priced_move_pct.toFixed(1)}%</span>
                </div>
              ) : null}
            </>
          ) : (
            <div className="caption dim">No report date on the calendar.</div>
          )}
        </Cell>

        <Cell label="Last quarter" href="#business">
          {quarter ? (
            <>
              <div className="passport-verdict">
                <span>Growth <strong className={quarter.verdict.growth === "REAL" ? "read-good"
                  : quarter.verdict.growth === "WEAK" ? "read-bad" : "read-neutral"}>
                  {quarter.verdict.growth}</strong></span>
                <span>Proof <strong className={quarter.verdict.proof === "SHOWN" ? "read-good" : "read-bad"}>
                  {quarter.verdict.proof}</strong></span>
              </div>
              <div className="caption dim">
                Quarter to {day(quarter.glance.end)}
                {quarter.glance.rev_yoy != null && <>, revenue {pct(quarter.glance.rev_yoy, 0)} on a year ago</>}
              </div>
            </>
          ) : (
            <div className="caption dim">
              {stock.fundamentals === null
                ? "No US GAAP filings to read."
                : "No filed quarter read yet."}
            </div>
          )}
        </Cell>
      </div>
    </header>
  );
}
