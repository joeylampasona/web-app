import type { DeskRun, DeskSignal } from "@/lib/types";

/**
 * Signals from the Market Desk — a separate overnight scanner that sweeps the
 * whole US market for filings, insider clusters, tape anomalies and sentiment.
 *
 * Kept visibly separate from everything else on the page, and labelled as
 * another system's reading rather than folded in as though this site computed
 * it. When it is wrong, it should be obvious whose it was.
 *
 * Two things carried through from its contract rather than dropped:
 * an unrecognised reason is shown plainly instead of being discarded, because
 * new ones appear within a major version; and a reading the desk marks as a
 * suspected corporate action is labelled, because an unadjusted reverse split
 * reads as a several-thousand-per-cent gap and is not a move anyone can trade.
 */
const SOURCE_LABEL: Record<string, string> = {
  FILING: "Filing", INSIDER: "Insider", TAPE: "Tape",
  SENTIMENT: "Chatter", EVENT: "Event",
};

const REASON_LABEL: Record<string, string> = {
  CLUSTER_BUY: "Several insiders bought",
  MASS_SELL: "Several insiders sold",
  BIG_INSIDER_BUY: "Large insider purchase",
  RED_FLAG: "Red flag in a filing",
  "13D_ACTIVIST": "An activist took a stake",
  VOLUME_SPIKE: "Unusual volume",
  GAP: "Gapped",
  "52W_HIGH": "New 52-week high",
  "52W_LOW": "New 52-week low",
  MENTION_SPIKE: "Spike in online mentions",
  EARNINGS_UPCOMING: "Earnings coming",
  EARNINGS_DATE_MOVED: "Earnings date moved",
};

/** 8-K item codes are the filing's own reference; spelling out the common ones
 *  is more use than the number, and the number is kept for the rest. */
function label(reason: string): string {
  if (REASON_LABEL[reason]) return REASON_LABEL[reason];
  const item = /^8K_(.+)$/.exec(reason);
  if (item) {
    const named: Record<string, string> = {
      "1.01": "Entered a material agreement",
      "2.02": "Reported results",
      "5.02": "A director or officer changed",
      "8.01": "Other material event",
    };
    return named[item[1]] ?? `8-K item ${item[1]}`;
  }
  // New reasons appear within a major version. Informational, not an error.
  return reason.replace(/_/g, " ").toLowerCase();
}

export function DeskSignals({
  signals, run,
}: {
  signals: DeskSignal[];
  run?: DeskRun | null;
}) {
  const broken = run
    ? Object.entries(run.stage_status).filter(([, v]) => v !== "ok")
    : [];

  if (!signals?.length) {
    return (
      <div className="stack" style={{ gap: "var(--gap-xs)" }}>
        <p className="muted footnote" style={{ margin: 0 }}>
          Nothing flagged for this company on the last market sweep.
        </p>
        {broken.length > 0 && <Degraded broken={broken} />}
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      {signals.map((s, i) => {
        const body = (
          <>
            <div className="between">
              <span className="footnote">{label(s.reason)}</span>
              <span className="caption dim">
                {SOURCE_LABEL[s.source] ?? s.source} · {s.as_of}
              </span>
            </div>
            {s.detail && (
              <div className="caption dim">
                {s.detail}
                {s.suspect && " — the scanner believes this is a corporate action "
                  + "rather than a real move."}
              </div>
            )}
          </>
        );
        return s.url ? (
          <a key={`${s.reason}-${i}`} href={s.url} target="_blank"
             rel="noopener noreferrer nofollow" className="card stack"
             style={{ gap: 2, padding: "var(--pad-md) var(--pad-lg)" }}>
            {body}
          </a>
        ) : (
          <div key={`${s.reason}-${i}`} className="card stack"
               style={{ gap: 2, padding: "var(--pad-md) var(--pad-lg)" }}>
            {body}
          </div>
        );
      })}
      {broken.length > 0 && <Degraded broken={broken} />}
      <p className="caption dim" style={{ margin: 0 }}>
        From a separate overnight market sweep, not from the screens on this
        site. What it flagged, not what it means.
      </p>
    </div>
  );
}

function Degraded({ broken }: { broken: [string, string][] }) {
  return (
    <p className="caption" style={{ color: "var(--warn)", margin: 0 }}>
      {broken.map(([k, v]) => `${k} (${v})`).join(", ")} did not run on the last
      sweep, so an empty result from {broken.length === 1 ? "it" : "them"} means
      nothing either way.
    </p>
  );
}
