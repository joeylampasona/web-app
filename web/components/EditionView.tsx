import Link from "next/link";
import type { Edition, EditionIndex } from "@/lib/types";
import { Headline } from "./HomeRead";

/**
 * A back issue: one night's front page, as it was read that night.
 *
 * Drawn with the home page's own parts (the headline under the highlighter,
 * the four-cell meter, the ratio bars, the layer bar) so an old edition
 * looks like the page it was, at a glance and without a legend. Nothing here
 * is recomputed with today's numbers: an edition is what was published on its
 * date, and a rebuilt one says which parts of the night were not kept.
 */
const STATE: Record<string, string> = { "1": "In gear", "0": "Neither", "-1": "Against" };
const RATIO_SCALE = 8;

export function weekday(iso: string, long = true): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", long
    ? { weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "UTC" }
    : { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
}

function signed(v: number): string {
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`;
}

/** The verdict as a tone, for the run of editions. */
export function tone(headline: string): "gear" | "against" | "mixed" | "unknown" {
  if (headline.includes("in gear")) return "gear";
  if (headline.includes("against")) return "against";
  if (headline.startsWith("Not enough")) return "unknown";
  return "mixed";
}

/** Every edition in the archive as one cell, oldest on the left, the way the
 *  breadth strip sets out the market: the run of reads is itself a reading. */
export function EditionRun({ index, current }: { index: EditionIndex; current?: string }) {
  const rows = [...index.editions].reverse();
  return (
    <div className="edition-run" role="list" aria-label="Every edition, oldest first">
      {rows.map((row) => (
        <Link key={row.date} href={`/market/editions/${row.date}`} role="listitem"
              className={`edition-run-cell edition-tone--${tone(row.headline)}`}
              aria-current={row.date === current ? "page" : undefined}
              title={`${weekday(row.date, false)}: ${row.headline}`}>
          <span className="visually-hidden">{weekday(row.date, false)}: {row.headline}</span>
        </Link>
      ))}
    </div>
  );
}

export function EditionView({ edition, index }: { edition: Edition; index: EditionIndex | null }) {
  const inGear = edition.meter.filter((c) => c.score === 1).length;
  const counts = edition.layers?.counts;
  return (
    <div className="stack" style={{ gap: "var(--pad-xl)" }}>
      <header className="screen-head" style={{ paddingBottom: 0 }}>
        <div className="stack" style={{ gap: "var(--gap-lg)" }}>
          <div className="kicker">
            Edition · {weekday(edition.date)}
            {edition.meter.length > 0 && <> · {inGear} of {edition.meter.length} checks in gear</>}
          </div>
          <h1 className="read-headline"><Headline text={edition.headline} /></h1>
          <p style={{ margin: 0, maxWidth: "58ch", fontSize: "var(--size-lead)",
                      color: "var(--text-secondary)" }}>
            {edition.blurb}
          </p>
        </div>
        <nav className="edition-nav" aria-label="Other editions">
          {edition.older
            ? <Link href={`/market/editions/${edition.older}`} className="control footnote">← {weekday(edition.older, false)}</Link>
            : <span className="control footnote" aria-disabled style={{ opacity: 0.4 }}>← The first kept</span>}
          {edition.newer
            ? <Link href={`/market/editions/${edition.newer}`} className="control footnote">{weekday(edition.newer, false)} →</Link>
            : <Link href="/" className="control footnote" aria-pressed="true">Tonight&rsquo;s page →</Link>}
        </nav>
      </header>

      {index && <EditionRun index={index} current={edition.date} />}

      {edition.meter.length > 0 && (
        <div className="stack" style={{ gap: "var(--gap-md)" }}>
          <div className="meter">
            {edition.meter.map((cell) => (
              <div key={cell.label} className="meter-cell"
                   data-lit={cell.score === 1 ? "true" : cell.score === -1 ? "against" : "false"}>
                <div className="label-caps" style={{ color: "var(--text-muted)" }}>{cell.label}</div>
                <div className="meter-value">{cell.value}</div>
                <div className="caption" style={{ color: "var(--text-secondary)" }}>
                  {STATE[String(cell.score)]}
                </div>
              </div>
            ))}
          </div>
          <ul className="footnote" style={{ margin: 0, paddingLeft: 18, color: "var(--text-secondary)" }}>
            {edition.checks.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </div>
      )}

      {edition.rebuilt && (
        <p className="footnote" style={{ margin: 0, borderLeft: "3px solid var(--rule)", paddingLeft: 12,
                                         color: "var(--text-secondary)", maxWidth: "70ch" }}>
          This edition was rebuilt. The read and its four checks are the same
          arithmetic on that session&rsquo;s published counts, but the rest of the
          night&rsquo;s page was not kept, so it stops here. Editions are kept in full
          from the night the archive began.
        </p>
      )}

      {(edition.radar || edition.tenths?.length) && (
        <div className="edition-split">
          {edition.radar && (
            <section className="stack" style={{ gap: "var(--gap-md)" }}>
              <div className="ruled-head"><h2>Where strength sat</h2><span className="kicker">six months</span></div>
              <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 28, lineHeight: 1.1 }}>
                {edition.radar.label}
              </div>
              <p className="footnote" style={{ margin: 0, color: "var(--text-secondary)" }}>{edition.radar.sub}</p>
              {edition.radar.pairs.map((p) => {
                if (p.rs126 == null) return null;
                const width = Math.min(50, (Math.abs(p.rs126) / RATIO_SCALE) * 50);
                const colour = p.rs126 >= 0 ? "var(--gain)" : "var(--loss)";
                return (
                  <div key={p.label} className="stack" style={{ gap: 5 }}>
                    <div className="between footnote">
                      <span style={{ fontWeight: 500 }}>{p.label}</span>
                      <span className="num" style={{ fontWeight: 600, color: colour }}>{signed(p.rs126)}</span>
                    </div>
                    <div className="diverge" aria-hidden>
                      <span className="bar" style={{ background: colour, width: `${width}%`,
                                                     left: p.rs126 >= 0 ? "50%" : `${50 - width}%` }} />
                      <span className="mid" />
                    </div>
                  </div>
                );
              })}
              <p className="caption dim" style={{ margin: 0 }}>
                {edition.radar.leaders.length > 0 && <>Leading: {edition.radar.leaders.join(", ")}. </>}
                {edition.radar.weakest.length > 0 && <>Weakest: {edition.radar.weakest.join(", ")}.</>}
              </p>
            </section>
          )}

          <section className="stack" style={{ gap: "var(--gap-md)" }}>
            {edition.tenths && edition.tenths.length > 0 && (
              <>
                <div className="ruled-head"><h2>The market in ten cells</h2><span className="kicker">breadth</span></div>
                <div className="tenths" role="img"
                     aria-label={`Share above both lines by tenth of the ranking, strongest first: ${edition.tenths.join("%, ")}%`}>
                  {edition.tenths.map((v, i) => (
                    <span key={i} className="num" style={{
                      background: v >= 50 ? `rgba(var(--heat-up), ${0.2 + 0.8 * (v - 50) / 50})`
                        : `rgba(var(--heat-down), ${0.2 + 0.8 * (50 - v) / 50})`,
                      color: v >= 80 || v <= 20 ? "#fff" : "var(--text-primary)",
                    }}>{v}%</span>
                  ))}
                </div>
                <div className="between caption dim"><span>Strongest tenth</span><span>Weakest tenth</span></div>
                <p className="caption dim" style={{ margin: 0 }}>
                  The share of each tenth of the ranking above both its 50-day and 200-day lines.
                </p>
              </>
            )}
            {counts && edition.layers && (
              <>
                <div className="ruled-head" style={{ marginTop: "var(--gap-lg)" }}>
                  <h2>Leadership layers</h2>
                  <span className="kicker">{counts.n.toLocaleString("en-US")} stocks</span>
                </div>
                <div className="layerbar" role="img"
                     aria-label={edition.layers.order.map((k) => `${edition.layers!.labels[k]} ${counts[k]}`).join(", ")}>
                  {edition.layers.order.map((k) => counts[k] > 0 && (
                    <span key={k} className={`layer--${k}`} style={{ flex: `${counts[k]} 1 0` }}
                          title={`${edition.layers!.labels[k]}: ${counts[k]}`} />
                  ))}
                </div>
                <div className="layer-key">
                  {edition.layers.order.map((k) => (
                    <div key={k} className="row" style={{ gap: "var(--gap-sm)", alignItems: "flex-start" }}>
                      <span aria-hidden className={`sw layer--${k}`} />
                      <span className="caption">{edition.layers!.labels[k]}{" "}
                        <span className="num" style={{ fontWeight: 600 }}>{counts[k]}</span></span>
                    </div>
                  ))}
                </div>
                {edition.layers.front.length > 0 && (
                  <div className="row wrap footnote" style={{ gap: "4px var(--gap-md)" }}>
                    <span className="label-caps hl" style={{ padding: "2px 8px" }}>Front line that night</span>
                    {edition.layers.front.map((symbol) => (
                      <Link key={symbol} href={`/stocks/${symbol}`} className="mono" style={{ fontWeight: 600 }}>
                        {symbol}
                      </Link>
                    ))}
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      )}

      <div className="edition-split">
        <section className="stack" style={{ gap: 0 }}>
          <div className="ruled-head"><h2>Breadth that session</h2></div>
          <div className="ruled-list">
            {edition.breadth.map((row) => (
              <div key={row.key} className="between footnote">
                <span>{row.label}</span>
                <span className="num" style={{ fontWeight: 600 }}>
                  {row.unit === "percent" ? `${row.value.toFixed(1)}%` : row.value.toFixed(0)}
                </span>
              </div>
            ))}
          </div>
        </section>
        {edition.screens && edition.screens.length > 0 && (
          <section className="stack" style={{ gap: 0 }}>
            <div className="ruled-head"><h2>On the screens</h2><span className="kicker">names</span></div>
            <div className="ruled-list">
              {edition.screens.map((row) => (
                <div key={row.key} className="between footnote">
                  <Link href={`/screens/${row.key}`}>{row.name}</Link>
                  <span className="num" style={{ fontWeight: 600 }}>{row.total}</span>
                </div>
              ))}
            </div>
            <p className="caption dim" style={{ margin: "var(--gap-sm) 0 0" }}>
              Counts as published that night. The links go to the screens as they stand now.
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
