import Link from "next/link";
import type {
  ScreenRecordFile, ScreenRecordHorizon, ScreenRecordRow, ScreenRecordStatus,
} from "@/lib/types";
import { shortDay } from "./CarriedOver";

/**
 * The record: every screen's results on one page, and which are on watch.
 *
 * The follow-through page lists each breakout. This counts them, by screen,
 * and applies one rule that is printed above the table in the same words the
 * code uses. A verdict here is a label and nothing more: an on-watch screen
 * keeps its place and every name on it. What changes is that the page says
 * so, with the numbers, instead of leaving a reader to work it out.
 *
 * Three states, three marks, no colour for the verdict. Colour on this site
 * means gain and loss, and a screen on watch is not a loss, it is a screen
 * whose last six months did not pay.
 */
export function RecordMark({ status, children }: {
  status: ScreenRecordStatus; children: React.ReactNode;
}) {
  return <span className={`record-mark record-${status}`}>{children}</span>;
}

function pct(value: number | null, signed = true): string {
  if (value == null) return "—";
  const sign = signed && value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(1)}%`;
}

function tone(value: number | null): string {
  return value == null ? "" : value > 0 ? "gain" : value < 0 ? "loss" : "";
}

function share(part: number, at: ScreenRecordHorizon): React.ReactNode {
  if (!at.n) return "—";
  return (
    <>
      {part} of {at.n}{" "}
      <span className="caption dim">{Math.round((100 * part) / at.n)}%</span>
    </>
  );
}

function JudgedRow({ row, horizon }: { row: ScreenRecordRow; horizon: string }) {
  const at = row.horizons[horizon];
  return (
    <>
      <tr className="record-row">
        <td className="text">
          <Link href={`/screens/${row.screen}`} className="record-name">{row.name}</Link>
        </td>
        <td className="text"><RecordMark status={row.status}>{row.label}</RecordMark></td>
        <td className="num">{row.total || "—"}</td>
        <td className="num" style={{ whiteSpace: "nowrap" }}>{at ? share(at.up, at) : "—"}</td>
        <td className="num" style={{ whiteSpace: "nowrap" }}>{at ? share(at.held, at) : "—"}</td>
        <td className={`num ${tone(at?.median_pct ?? null)}`} style={{ fontWeight: 600 }}>
          {pct(at?.median_pct ?? null)}
        </td>
        <td className={`num ${tone(at?.mean_pct ?? null)}`}>{pct(at?.mean_pct ?? null)}</td>
        <td className="num">{pct(at?.bench_median_pct ?? null)}</td>
        <td className={`num ${tone(at?.median_vs_bench_pct ?? null)}`}>
          {at?.median_vs_bench_pct == null ? "—"
            : `${at.median_vs_bench_pct > 0 ? "+" : at.median_vs_bench_pct < 0 ? "−" : ""}${Math.abs(at.median_vs_bench_pct).toFixed(1)} pts`}
        </td>
      </tr>
      <tr className="record-why">
        <td className="text caption" colSpan={9}>{row.reason}</td>
      </tr>
    </>
  );
}

function OtherHorizons({ file, judged }: { file: ScreenRecordFile; judged: string }) {
  const others = file.horizons.map(String).filter((h) => h !== judged);
  const rows = file.screens.filter((row) => row.measured);
  if (!others.length || !rows.length) return null;
  return (
    <section className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="ruled-head">
        <h2 style={{ margin: 0 }}>At the other horizons</h2>
        <span className="kicker">Not part of the rule</span>
      </div>
      <div className="scroll-x card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th className="text">Screen</th>
              {others.map((h) => (
                <th key={h} colSpan={4} className="record-group">{h} sessions on</th>
              ))}
            </tr>
            <tr>
              <th className="text" />
              {others.map((h) => (
                <RecordSubhead key={h} benchmark={file.benchmark} />
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.screen}>
                <td className="text">{row.name}</td>
                {others.map((h) => {
                  const at = row.horizons[h];
                  return (
                    <RecordCells key={h} at={at} />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RecordSubhead({ benchmark }: { benchmark: string }) {
  return (
    <>
      <th>Up</th>
      <th>Held</th>
      <th>Median</th>
      <th>vs {benchmark}</th>
    </>
  );
}

function RecordCells({ at }: { at: ScreenRecordHorizon | undefined }) {
  if (!at || !at.n) {
    return (
      <>
        <td className="num dim">—</td><td className="num dim">—</td>
        <td className="num dim">—</td><td className="num dim">—</td>
      </>
    );
  }
  return (
    <>
      <td className="num" style={{ whiteSpace: "nowrap" }}>{share(at.up, at)}</td>
      <td className="num" style={{ whiteSpace: "nowrap" }}>{share(at.held, at)}</td>
      <td className={`num ${tone(at.median_pct)}`}>{pct(at.median_pct)}</td>
      <td className={`num ${tone(at.median_vs_bench_pct)}`}>
        {at.median_vs_bench_pct == null ? "—"
          : `${at.median_vs_bench_pct > 0 ? "+" : at.median_vs_bench_pct < 0 ? "−" : ""}${Math.abs(at.median_vs_bench_pct).toFixed(1)}`}
      </td>
    </>
  );
}

export function ScreenRecord({ file }: { file: ScreenRecordFile }) {
  const judged = String(file.rule.judge_horizon);
  const measured = file.screens.filter((row) => row.measured);
  const unmeasured = file.screens.filter((row) => !row.measured);
  const months = file.window_days ? Math.round(file.window_days / 30) : 6;
  const asOf = shortDay(file.as_of);

  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      <section className="record-rule stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="eyebrow">The rule</div>
        <p style={{ margin: 0, maxWidth: "74ch" }}>{file.rule.text}</p>
        <p className="caption dim" style={{ margin: 0 }}>
          {file.counts.holding} holding · {file.counts.on_watch} on watch ·{" "}
          {file.counts.too_few} too few to judge
          {asOf ? ` · counted through ${asOf}` : ""}
        </p>
      </section>

      <section className="stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="ruled-head">
          <h2 style={{ margin: 0 }}>{judged} sessions after the breakout</h2>
          <span className="kicker">Last {months} months</span>
        </div>
        <div className="scroll-x card" style={{ padding: 0 }}>
          <table className="data record-table">
            <thead>
              <tr>
                <th className="text">Screen</th>
                <th className="text">Verdict</th>
                <th>Breakouts</th>
                <th>Up</th>
                <th>Above the pivot</th>
                <th>Median</th>
                <th>Mean</th>
                <th>{file.benchmark}, same sessions</th>
                <th>Against it</th>
              </tr>
            </thead>
            <tbody>
              {measured.map((row) => (
                <JudgedRow key={row.screen} row={row} horizon={judged} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>
          Breakouts is every one in the window; Up and Above the pivot count only
          those old enough to have run {judged} sessions. {file.copy.held}{" "}
          {file.copy.baseline}
        </p>
      </section>

      <OtherHorizons file={file} judged={judged} />

      {unmeasured.length > 0 && (
        <section className="stack" style={{ gap: "var(--gap-sm)" }}>
          <div className="ruled-head">
            <h2 style={{ margin: 0 }}>No record yet</h2>
            <span className="kicker">{unmeasured.length} screens</span>
          </div>
          <p style={{ margin: 0, maxWidth: "74ch" }}>
            {unmeasured.map((row, index) => (
              <span key={row.screen}>
                {index > 0 && ", "}
                <Link href={`/screens/${row.screen}`} className="record-name">{row.name}</Link>
              </span>
            ))}
            .
          </p>
          <p className="footnote muted" style={{ margin: 0, maxWidth: "74ch" }}>
            {unmeasured[0].reason} They are &ldquo;too few to judge&rdquo; with nothing
            counted, which is not the same as holding.
          </p>
        </section>
      )}

      <p className="footnote muted" style={{ margin: 0, maxWidth: "78ch" }}>
        {file.copy.survivorship} Every breakout behind these counts is listed on{" "}
        <Link href="/market/followthrough" style={{ color: "var(--link)", textDecoration: "underline" }}>
          Did it work?
        </Link>{" "}
        What else has been tested, and how it came out, is in{" "}
        <Link href="/market/research" style={{ color: "var(--link)", textDecoration: "underline" }}>
          the ledger
        </Link>.
      </p>
    </div>
  );
}

/**
 * The record's verdict where the screen itself is read: under its masthead.
 *
 * Holding says nothing here, because a page that congratulates itself every
 * night is noise. On watch says so in full, with the numbers. Too few says
 * that there is no verdict, in one quiet line.
 */
export function RecordNote({ row }: { row: ScreenRecordRow | undefined }) {
  if (!row) return null;
  if (row.status === "holding") {
    return (
      <p className="caption dim record-note">
        <RecordMark status="holding">Holding</RecordMark>{" "}{row.reason}{" "}
        <Link href="/market/record" style={{ textDecoration: "underline" }}>The record</Link>
      </p>
    );
  }
  if (row.status === "on_watch") {
    return (
      <p className="footnote record-note record-note-watch">
        <RecordMark status="on_watch">On watch</RecordMark>{" "}
        {row.reason} The screen is unchanged and every name is still on it; this
        says how its last breakouts went.{" "}
        <Link href="/market/record" style={{ textDecoration: "underline" }}>The record</Link>
      </p>
    );
  }
  return (
    <p className="caption dim record-note">
      <RecordMark status="too_few">Too few to judge</RecordMark>{" "}{row.reason}{" "}
      <Link href="/market/record" style={{ textDecoration: "underline" }}>The record</Link>
    </p>
  );
}

/** One line for the home page: the count of each, and the way in. */
export function RecordLine({ file }: { file: ScreenRecordFile | null }) {
  if (!file) return null;
  const watch = file.screens.filter((row) => row.status === "on_watch");
  return (
    <p className="footnote muted record-line" style={{ margin: 0 }}>
      <span className="label-caps">The record</span>{" "}
      {file.counts.holding} screens holding, {file.counts.on_watch} on watch
      {watch.length > 0 && ` (${watch.map((row) => row.name).join(", ")})`},{" "}
      {file.counts.too_few} too few to judge.{" "}
      <Link href="/market/record" style={{ color: "var(--link)", textDecoration: "underline" }}>
        How each screen&rsquo;s breakouts went
      </Link>
    </p>
  );
}
