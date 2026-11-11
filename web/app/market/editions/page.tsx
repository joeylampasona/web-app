import Link from "next/link";
import { DataBanner, NoData } from "@/components/DataBanner";
import { EditionRun, tone, weekday } from "@/components/EditionView";
import { getEditions, getMeta, hasData } from "@/lib/data";

export const metadata = { title: "Back issues" };

/**
 * The archive: every night's front page that was kept, newest first.
 *
 * A row is the edition at a glance (its read, its four checks as four small
 * cells, the radar's label, breakouts against failures) and opens the page as
 * it stood that night.
 */
export default function EditionsPage() {
  if (!hasData()) return <NoData />;
  const index = getEditions();
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <header className="screen-head">
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          <div className="kicker">Market · back issues{index ? ` · ${index.count} kept` : ""}</div>
          <h1 className="passport-name">Back issues</h1>
          <p className="muted" style={{ margin: 0, maxWidth: "62ch" }}>
            Each night&rsquo;s read, kept as it was published, so what the page said
            before a move can be checked afterwards. Nothing in an edition is
            revised with later numbers.
          </p>
        </div>
      </header>

      {!index || index.editions.length === 0 ? (
        <p className="muted footnote">
          No editions have been kept yet. The archive starts with the next nightly run.
        </p>
      ) : (
        <div className="stack" style={{ gap: "var(--pad-lg)" }}>
          <div className="stack" style={{ gap: "var(--gap-xs)" }}>
            <EditionRun index={index} />
            <div className="row wrap caption dim" style={{ gap: "4px var(--gap-lg)" }}>
              <span>One cell per edition, oldest on the left.</span>
              <span><span className="edition-key edition-tone--gear" /> in gear</span>
              <span><span className="edition-key edition-tone--mixed" /> mixed</span>
              <span><span className="edition-key edition-tone--against" /> against breakouts</span>
            </div>
          </div>

          <div className="scroll-x">
            <table className="data edition-table">
              <thead>
                <tr>
                  <th className="text">Session</th><th className="text">The read</th>
                  <th className="text">Checks</th><th className="text">Where strength sat</th>
                  <th title="Cleared a pivot : tested one and fell back">Breakouts : failed</th>
                  <th>Front line</th>
                </tr>
              </thead>
              <tbody>
                {index.editions.map((row) => (
                  <tr key={row.date}>
                    <td className="text mono" style={{ whiteSpace: "nowrap" }}>
                      <Link href={`/market/editions/${row.date}`}>{weekday(row.date, false)}</Link>
                    </td>
                    <td className="text">
                      <Link href={`/market/editions/${row.date}`} style={{ fontWeight: 600 }}>
                        <span className={tone(row.headline) === "gear" ? "hl" : undefined}>{row.headline}</span>
                      </Link>
                      {row.rebuilt && <span className="caption dim"> · rebuilt</span>}
                    </td>
                    <td className="text">
                      <span className="edition-checks" role="img"
                            aria-label={`${row.scores.filter((s) => s === 1).length} of ${row.scores.length} in gear`}>
                        {row.scores.map((score, i) => (
                          <span key={i} data-score={score} />
                        ))}
                      </span>
                    </td>
                    <td className="text">{row.label ?? <span className="dim">not kept</span>}</td>
                    <td className="num">
                      {row.breakouts == null || row.failed == null ? "—"
                        : `${row.breakouts.toFixed(0)} : ${row.failed.toFixed(0)}`}
                    </td>
                    <td className="num">{row.front ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="caption dim" style={{ margin: 0, maxWidth: "70ch" }}>
            Editions marked rebuilt were recomputed from the session&rsquo;s published
            breadth counts when the archive began: the read and its four checks,
            nothing else. About a year of sessions is kept.
          </p>
        </div>
      )}
    </div>
  );
}
