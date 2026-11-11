"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CatalystCountdown } from "./CatalystCountdown";
import { CatalystTimeline } from "./CatalystTimeline";
import { DeskSignals } from "./DeskSignals";
import { CriteriaMeter } from "./CriteriaMeter";
import { GatedForecastPanel } from "./GatedForecastPanel";
import { GatedEarningsMoves } from "./EarningsMoves";
import { EarningsPriced } from "./EarningsPriced";
import { FundamentalsPanel } from "./FundamentalsPanel";
import { GatedHolders } from "./Holders";
import { levelLines, LevelsPanel } from "./LevelsPanel";
import { StockLeadership } from "./Leadership";
import { StockPassport } from "./StockPassport";
import { GatedXRay } from "./GatedXRay";
import { GatedGammaPanel } from "./GatedGammaPanel";
import { InsiderPanel } from "./InsiderPanel";
import { MovingAverageKey } from "./MovingAverageKey";
import { NewsPanel } from "./NewsPanel";
import { PeerBars } from "./PeerBars";
import { SetupChart } from "./SetupChart";
import { ShapeReadout } from "./ShapeReadout";
import { StructureCheck } from "./StructureCheck";
import { StockCard } from "./StockCard";
import { rsText } from "@/lib/format";
import { planMovingAverages } from "@/lib/movingAverages";
import type { DeskRun, StockFile } from "@/lib/types";

// Stable empties, so the chart is not rebuilt on every render.
const NONE: never[] = [];
const NONE_FLAGS: string[] = [];

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

export function StockDetail({ stock, run }: {
  stock: StockFile;
  /** Which of the market sweep's scanners worked — so an empty signal
   *  set can be told apart from a scanner that did not run. */
  run?: DeskRun | null;
}) {
  const setup = stock.primary_setup;
  // The shape screens publish a fitted geometry; the base screens do not.
  const shaped = stock.setups.filter((s) => s.shape);

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

  const lines = useMemo(() => levelLines(stock.levels), [stock.levels]);
  const [layers, setLayers] = useState({ base: true, averages: true, levels: false });
  const flip = (key: keyof typeof layers) =>
    setLayers((held) => ({ ...held, [key]: !held[key] }));
  const toggles = (
    <div className="chart-layers" role="group" aria-label="What the chart draws">
      <span className="label-caps" style={{ color: "var(--text-muted)" }}>Draw</span>
      {setup && (
        <button type="button" aria-pressed={layers.base} onClick={() => flip("base")}>
          <span aria-hidden className="swatch" style={{ borderTop: "2px dashed var(--chart-pivot, var(--warn))" }} />
          Base and pivot
        </button>
      )}
      <button type="button" aria-pressed={layers.averages} onClick={() => flip("averages")}>
        <span aria-hidden className="swatch" style={{ borderTop: "2px solid var(--chart-ma-50)" }} />
        Averages
      </button>
      {lines.length > 0 && (
        <button type="button" aria-pressed={layers.levels} onClick={() => flip("levels")}>
          <span aria-hidden className="swatch" style={{ borderTop: "2px dotted var(--text-secondary)" }} />
          Levels <span className="num dim">{lines.length}</span>
        </button>
      )}
    </div>
  );

  return (
    <div className="stack" style={{ gap: "var(--pad-xl)" }}>
      <StockPassport stock={stock} />

      {/* One chart. The page used to draw the same hundred and forty sessions
          three times: once with the base, once with the averages, once with
          the levels. They are layers of one picture, so they are switches on
          one chart, and a reader can see a pivot against a level against the
          50-day line without holding two charts in their head. */}
      <div id="chart" style={{ scrollMarginTop: 120 }}>
        {setup ? (
          <StockCard setup={setup} bars={chartBars} chartHeight="responsive"
                     showHeader={false} strip
                     overlays={{ base: layers.base,
                                 movingAverages: layers.averages ? maPlan : null,
                                 levels: layers.levels ? lines : null }}
                     chartHead={toggles}
                     chartFoot={layers.averages
                       ? <MovingAverageKey plan={maPlan} stacked={setup.trend?.stacked} /> : null} />
        ) : (
          <div id="structure" className="stack" style={{ gap: "var(--gap-sm)", scrollMarginTop: 120 }}>
            <StructureCheck rows={stock.structure_check} name={stock.symbol} />
            {chartBars.length > 0 && (
              <div className="card stack" style={{ padding: "var(--pad-md)",
                                                   gap: "var(--gap-sm)" }}>
                {toggles}
                <SetupChart
                  bars={chartBars}
                  pivot={null}
                  contractions={NONE}
                  breakoutDate={null}
                  flags={NONE_FLAGS}
                  symbol={stock.symbol}
                  height="responsive"
                  movingAverages={layers.averages ? maPlan : null}
                  levels={layers.levels ? lines : null}
                />
                {layers.averages && <MovingAverageKey plan={maPlan} />}
              </div>
            )}
          </div>
        )}
      </div>

      {stock.levels !== undefined && (
        <section className="stack" style={{ gap: "var(--gap-sm)" }}>
          <div className="eyebrow">Support and resistance</div>
          <LevelsPanel summary={stock.levels} symbol={stock.symbol}
                       onShow={() => {
                         setLayers((held) => ({ ...held, levels: true }));
                         document.getElementById("chart")?.scrollIntoView({ behavior: "smooth" });
                       }} />
        </section>
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

      {stock.leadership !== undefined && (
        <section id="industry">
          <div className="eyebrow">Against its industry</div>
          <StockLeadership r={stock.leadership} />
        </section>
      )}

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
          <div className="card stack" style={{ gap: "var(--gap-sm)" }}>
            <div className="footnote muted">Same industry</div>
            <PeerBars peers={stock.peers.industry} self={stock.symbol} empty="None" />
          </div>
          <div className="card stack" style={{ gap: "var(--gap-sm)" }}>
            <div className="footnote muted">Same theme</div>
            <PeerBars peers={stock.peers.theme} self={stock.symbol}
                      empty="No themes — common and fine." />
          </div>
        </div>
      </section>

      <section id="roadmap">
        <div className="eyebrow">Catalyst roadmap</div>
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          <CatalystCountdown events={stock.catalyst_roadmap} />
          <CatalystTimeline events={stock.catalyst_roadmap} />
        </div>
      </section>

      <section>
        <div className="eyebrow">How it moves on earnings</div>
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          <EarningsPriced next={stock.earnings_priced} last={stock.earnings_priced_last}
                          usual={stock.earnings_moves} />
          <GatedEarningsMoves symbol={stock.symbol} moves={stock.earnings_moves}
                              locked={Boolean(stock.earnings_moves_gated)} />
        </div>
      </section>

      {stock.fundamentals !== undefined && (
        <section id="business">
          <div className="eyebrow">The business</div>
          <FundamentalsPanel f={stock.fundamentals} symbol={stock.symbol} name={stock.name} />
        </section>
      )}

      {stock.holders !== undefined && (
        <section>
          <div className="eyebrow">Tracked funds</div>
          <GatedHolders symbol={stock.symbol} counts={stock.holders}
                        locked={Boolean(stock.holders_gated)} />
        </section>
      )}

      <section>
        <div className="eyebrow">Flagged by the market sweep</div>
        <DeskSignals signals={stock.desk_signals} run={run} />
      </section>

      <section>
        <div className="eyebrow">In the news</div>
        <NewsPanel news={stock.news} symbol={stock.symbol} />
      </section>

      <section>
        <div className="eyebrow">Insiders</div>
        <InsiderPanel insiders={stock.insiders} />
      </section>

      {shaped.length > 0 && (
        <section>
          <div className="eyebrow">The geometry</div>
          {/* Every shape this stock is currently inside, not just the one the
              publisher picked as primary. A name on both the triangle and the
              descending-triangle screen is inside two readings of the same
              price action, and showing one of them silently would make the
              other screen's listing look unexplained. */}
          <div className="stack" style={{ gap: "var(--gap-lg)" }}>
            {shaped.map((s) => (
              <div key={s.screen} className="stack" style={{ gap: "var(--gap-sm)" }}>
                {shaped.length > 1 && (
                  <div className="footnote muted">{s.screen.replace(/_/g, " ")}</div>
                )}
                {/* The formation drawn, next to the numbers describing it. Not
                    on the card at the top of the page: that one draws whichever
                    setup the publisher picked as primary, which for a stock on
                    both a base screen and a shape screen is usually the base —
                    so the wedge would have been described here and drawn
                    nowhere. */}
                {chartBars.length > 0 && (
                  <SetupChart
                    bars={chartBars}
                    pivot={s.pivot}
                    contractions={[]}
                    breakoutDate={s.breakout_date}
                    flags={[]}
                    symbol={`${stock.symbol}-${s.screen}`}
                    height="responsive"
                    shape={s.shape}
                  />
                )}
                <ShapeReadout shape={s.shape} />
              </div>
            ))}
          </div>
        </section>
      )}

      {setup?.criteria && (
        <section>
          <div className="eyebrow">What lines up</div>
          <CriteriaMeter criteria={setup.criteria} detailed />
        </section>
      )}

      <section>
        <div className="eyebrow">What analysts expect</div>
        <GatedForecastPanel symbol={stock.symbol} forecast={stock.forecast}
                            locked={Boolean(stock.forecast_gated)} />
      </section>

      <section>
        <div className="eyebrow">Gamma concentration</div>
        <GatedGammaPanel symbol={stock.symbol} gamma={stock.gamma}
                         locked={Boolean(stock.gamma_gated)} />
      </section>
      </div>

      {/* Full width: it is a chart of every base this stock has built, and
          halving it would defeat the point of showing them together. */}
      <section>
        <div className="eyebrow">X-ray</div>
        <GatedXRay symbol={stock.symbol} bars={stock.bars}
                   bases={stock.base_history}
                   total={stock.base_history_total ?? stock.base_history.length}
                   locked={Boolean(stock.xray_gated)} />
      </section>
    </div>
  );
}
