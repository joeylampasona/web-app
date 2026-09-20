"use client";

import Link from "next/link";
import { useMemo } from "react";
import { AuthGate } from "./AuthGate";
import { CatalystTimeline } from "./CatalystTimeline";
import { DeskSignals } from "./DeskSignals";
import { CriteriaMeter } from "./CriteriaMeter";
import { GammaPanel } from "./GammaPanel";
import { InsiderPanel } from "./InsiderPanel";
import { MovingAverageKey } from "./MovingAverageKey";
import { NewsPanel } from "./NewsPanel";
import { SetupChart } from "./SetupChart";
import { StockCard } from "./StockCard";
import { WatchStar } from "./WatchStar";
import { XRayChart } from "./XRayChart";
import { QuadrantBadge } from "./Badges";
import { compactMoney, rsText } from "@/lib/format";
import { planMovingAverages } from "@/lib/movingAverages";
import type { DeskRun, StockFile } from "@/lib/types";

/** Reads plainly, and never says what the stock is going to do next. */
function plainRead(stock: StockFile): string {
  const setup = stock.primary_setup;
  const rank = rsText(stock.rs_rating);
  if (!setup) {
    return `${stock.name} is not on any of the screens right now. Its relative ` +
      `strength rating is ${rank}, and it sits in ${stock.industry}.`;
  }
  const weeks = setup.base_weeks?.toFixed(1) ?? "—";
  const depth = setup.base_depth_pct?.toFixed(0) ?? "—";
  const gap = setup.now_vs_pivot_pct ?? 0;
  const where = gap >= 0
    ? `${gap.toFixed(1)}% above that pivot`
    : `${Math.abs(gap).toFixed(1)}% below it`;
  return `The base has run ${weeks} weeks and fell ${depth}% from its ceiling at its ` +
    `deepest. The pivot is $${setup.pivot.toFixed(2)}, and the stock closed ${where}. ` +
    `Its relative strength rating is ${rank}.`;
}

/** The chip class for a quadrant, or nothing when the group has none.
 *  These four colours are already computed for every name; they were only ever
 *  shown on one badge. */
function quadrantChip(quadrant: string | null): string {
  switch (quadrant) {
    case "powering": return "chip--powering";
    case "turning": return "chip--turning";
    case "cooling": return "chip--cooling";
    case "falling": return "chip--falling";
    default: return "";
  }
}

export function StockDetail({ stock, run }: {
  stock: StockFile;
  /** Which of the market sweep's scanners worked — so an empty signal
   *  set can be told apart from a scanner that did not run. */
  run?: DeskRun | null;
}) {
  const setup = stock.primary_setup;

  // One slice and one plan, shared by the chart and the key beneath it. Both
  // are memoised because a fresh array on every render would rebuild the chart
  // on every render.
  const chartBars = useMemo(() => stock.bars.slice(-140), [stock.bars]);
  const maPlan = useMemo(
    () => planMovingAverages(
      chartBars.map((b) => b.close),
      // Absent and empty mean different things here — a file written before
      // moving averages existed, versus a stock with under a year of history —
      // so the distinction is passed through rather than flattened.
      stock.sma200 ? stock.sma200.slice(-chartBars.length) : stock.sma200,
    ),
    [chartBars, stock.sma200],
  );

  return (
    <div className="stack" style={{ gap: "var(--pad-xl)" }}>
      <div>
        <div className="between" style={{ marginBottom: "var(--gap-sm)" }}>
          <div>
            <h1 style={{ fontSize: "var(--size-h2)" }}>{stock.name}</h1>
            <div className="num dim footnote">
              {stock.symbol} · {stock.industry} · {compactMoney(stock.market_cap)}
            </div>
          </div>
          <div className="row" style={{ gap: "var(--gap-sm)", alignItems: "center" }}>
            {/* Always here. It used to be drawn only by the StockCard below,
                which renders only when the name is on a screen — so any stock
                that was not could not be added to a watchlist from anywhere. */}
            <WatchStar symbol={stock.symbol} withLabel />
            <QuadrantBadge quadrant={stock.quadrant} />
          </div>
        </div>
        {stock.themes.length > 0 && (
          <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
            {stock.themes.map((slug) => (
              <Link key={slug} href={`/themes/${slug}`}
                    className={`badge ${quadrantChip(stock.quadrant)}`}>{slug}</Link>
            ))}
          </div>
        )}
      </div>

      {setup ? (
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          <StockCard setup={setup} bars={chartBars} chartHeight="responsive" />
          {/* Drawn only here, never on a card in a list: four lines on a chart
              the size of a business card is noise, and this is the page someone
              reached by looking one company up. */}
          {chartBars.length > 0 && (
            <div className="card stack" style={{ padding: "var(--pad-md)",
                                                 gap: "var(--gap-sm)" }}>
              <div className="eyebrow">Moving averages</div>
              <SetupChart
                bars={chartBars}
                pivot={null}
                contractions={[]}
                breakoutDate={null}
                flags={[]}
                symbol={`${stock.symbol}-ma`}
                height="responsive"
                movingAverages={maPlan}
              />
              <MovingAverageKey plan={maPlan} stacked={setup.trend?.stacked} />
            </div>
          )}
        </div>
      ) : (
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          <div className="card muted footnote">
            Not on a screen at the moment — no base, so no pivot to draw. The price
            and volume are below.
          </div>
          {chartBars.length > 0 && (
            <div className="card stack" style={{ padding: "var(--pad-md)",
                                                 gap: "var(--gap-sm)" }}>
              <SetupChart
                bars={chartBars}
                pivot={null}
                contractions={[]}
                breakoutDate={null}
                flags={[]}
                symbol={stock.symbol}
                height="responsive"
                movingAverages={maPlan}
              />
              <MovingAverageKey plan={maPlan} />
            </div>
          )}
        </div>
      )}

      {/* Below the chart the page stops being one column on a wide screen.
          These sections are independent readings of the same stock, so they sit
          side by side rather than making the reader scroll past six of them to
          reach the seventh. One column on a phone, unchanged. */}
      <div className="detail-sections">
      <section>
        <div className="eyebrow">The read</div>
        <p className="muted footnote">{plainRead(stock)}</p>
      </section>

      {stock.setups.length > 1 && (
        <section>
          <div className="eyebrow">Also on</div>
          <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
            {stock.setups.map((s) => (
              <Link key={s.screen} href={`/screens/${s.screen}`} className="badge">
                {s.screen.replace("_", " ")} · {s.stage.replace("_", " ")}
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="eyebrow">Peers</div>
        <div className="grid-2">
          <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="footnote muted">Same industry</div>
            {stock.peers.industry.map((peer) => (
              <Link key={peer.symbol} href={`/stocks/${peer.symbol}`} className="between footnote">
                <span className="mono">{peer.symbol}</span>
                <span className="num dim">{rsText(peer.rs_rating)}</span>
              </Link>
            ))}
            {stock.peers.industry.length === 0 && <span className="caption dim">None</span>}
          </div>
          <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="footnote muted">Same theme</div>
            {stock.peers.theme.map((peer) => (
              <Link key={peer.symbol} href={`/stocks/${peer.symbol}`} className="between footnote">
                <span className="mono">{peer.symbol}</span>
                <span className="num dim">{rsText(peer.rs_rating)}</span>
              </Link>
            ))}
            {stock.peers.theme.length === 0 && (
              <span className="caption dim">No themes — common and fine.</span>
            )}
          </div>
        </div>
      </section>

      <section>
        <div className="eyebrow">Catalyst roadmap</div>
        <CatalystTimeline events={stock.catalyst_roadmap} />
      </section>

      <section>
        <div className="eyebrow">Flagged by the market sweep</div>
        <DeskSignals signals={stock.desk_signals} run={run} />
      </section>

      <section>
        <div className="eyebrow">In the news</div>
        <NewsPanel news={stock.news} />
      </section>

      <section>
        <div className="eyebrow">Insiders</div>
        <InsiderPanel insiders={stock.insiders} />
      </section>

      {setup?.criteria && (
        <section>
          <div className="eyebrow">What lines up</div>
          <CriteriaMeter criteria={setup.criteria} detailed />
        </section>
      )}

      <section>
        <div className="eyebrow">Gamma concentration</div>
        <GammaPanel gamma={stock.gamma} />
      </section>
      </div>

      {/* Full width: it is a chart of every base this stock has built, and
          halving it would defeat the point of showing them together. */}
      <section>
        <div className="eyebrow">X-ray</div>
        <AuthGate
          reason="See every base this stock has built"
          blurb="The X-ray puts all of them on one chart, so you can see how this
                 structure compares with the ones before it."
        >
          <div className="card">
            <XRayChart bars={stock.bars} bases={stock.base_history} />
          </div>
        </AuthGate>
      </section>
    </div>
  );
}
