import type { LedgerEntry, LedgerFile, LedgerVerdict } from "@/lib/types";

/**
 * The research ledger: every question this project has put to real data.
 *
 * Set as a register and not as a blog. Each entry is the same five things in
 * the same order (what was asked, what was measured, what came back, the
 * verdict, where it is written down), so a reader can run an eye down the
 * verdicts the way they would down a column of figures. The failures are in
 * the same type at the same size as the rest. That is the point of keeping
 * them.
 */
const ORDER: LedgerVerdict[] = ["adopted", "held", "refuted", "refused", "open"];

const WORD: Record<LedgerVerdict, string> = {
  adopted: "Adopted", held: "Held", refuted: "Refuted", refused: "Refused", open: "Open",
};

function day(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC",
  });
}

function Entry({ entry }: { entry: LedgerEntry }) {
  return (
    <article className="ledger-entry" id={entry.id}>
      <div className="ledger-margin">
        <div className="mono ledger-id">{entry.id}</div>
        <div className="caption dim">{day(entry.date)}</div>
        <div className={`ledger-verdict ledger-${entry.verdict}`}>{WORD[entry.verdict]}</div>
      </div>
      <div className="stack" style={{ gap: "var(--gap-sm)", minWidth: 0 }}>
        <h2 className="ledger-question">{entry.question}</h2>
        <dl className="ledger-body">
          <dt>Measured</dt>
          <dd>{entry.measured}</dd>
          <dt>Result</dt>
          <dd>{entry.result}</dd>
          {entry.waiting_for && (
            <>
              <dt>Waiting for</dt>
              <dd>{entry.waiting_for}</dd>
            </>
          )}
          <dt>Recorded in</dt>
          <dd className="mono ledger-source">
            {entry.source.map((source) => <div key={source}>{source}</div>)}
          </dd>
        </dl>
      </div>
    </article>
  );
}

export function Ledger({ file }: { file: LedgerFile }) {
  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      <section className="stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="eyebrow">{file.entries.length} questions</div>
        <dl className="ledger-key">
          {ORDER.map((verdict) => (
            <div key={verdict} className="ledger-key-row">
              <dt>
                <span className={`ledger-verdict ledger-${verdict}`}>{WORD[verdict]}</span>
                <span className="mono dim"> {file.counts[verdict] ?? 0}</span>
              </dt>
              <dd className="caption">{file.verdicts[verdict]}</dd>
            </div>
          ))}
        </dl>
        {file.note && (
          <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>{file.note}</p>
        )}
      </section>

      <div className="ledger">
        {file.entries.map((entry) => <Entry key={entry.id} entry={entry} />)}
      </div>

      <p className="footnote muted" style={{ margin: 0, maxWidth: "78ch" }}>
        An entry says only what the repository records, and names where. A
        question that came out against the idea stays in the list at the same
        size as one that held. Adding a study is adding an entry to
        <span className="mono"> research/ledger.yaml</span>; the nightly checks the
        file and a bad entry stops the build.
      </p>
    </div>
  );
}
