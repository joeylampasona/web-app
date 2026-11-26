import type { MarketContextFile } from "@/lib/types";

/**
 * Two readings this site does not compute itself, from the Market Desk: how
 * many puts are trading against calls at CBOE, and the desk's own regime read.
 *
 * Shown as readings with their dates, not as signals. A put/call ratio says
 * what option buyers did yesterday; it is often read as a contrarian gauge,
 * and the evidence for that is mixed, so the page states the ratio and what
 * it measures and stops there. Each carries its own date because the desk
 * nulls a stale one rather than repeating it, and a reading without its date
 * would hide which day it is from.
 */
function ratio(v: number | null | undefined): string {
  return v == null ? "—" : v.toFixed(2);
}

function day(iso: string | undefined | null): string {
  if (!iso) return "";
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", timeZone: "UTC",
  });
}

const REGIME_TONE: Record<string, string> = {
  "risk-on": "var(--gain)",
  stressed: "var(--loss)",
};

/** Scheduled macro releases inside the next five sessions, in one line.
 *  Nothing when there are none, which is most nights. */
function Crossing({ file }: { file: MarketContextFile }) {
  const events = (file.events_crossing ?? []).filter((e) => e && e.date && (e.label || e.name));
  if (events.length === 0) return null;
  return (
    <p className="caption dim" style={{ margin: 0 }}>
      Inside the next five sessions:{" "}
      {events.map((e, i) => (
        <span key={`${e.date}-${e.name}`}>
          {i > 0 && " · "}
          <span style={{ color: "var(--text-primary)" }}>{e.label || e.name}</span> {day(e.date)}
        </span>
      ))}
      . A scheduled release moves the whole tape and says nothing about one name.
    </p>
  );
}

export function MarketContext({ file, compact = false }: {
  file: MarketContextFile | null; compact?: boolean;
}) {
  if (!file) return null;
  const crossing = (file.events_crossing ?? []).length > 0;
  if (!file.put_call && !file.regime && !crossing) return null;
  const pc = file.put_call;
  const regime = file.regime;

  if (compact) {
    return (
      <>
        {(pc || regime) && (
          <p className="caption dim" style={{ margin: 0 }}>
            {pc && <>Put/call {ratio(pc.total)} (stocks {ratio(pc.equity)}), {day(pc.as_of)}</>}
            {pc && regime && " · "}
            {regime && (
              <>Market Desk reads the regime as{" "}
                <span style={{ color: REGIME_TONE[regime.label] }}>{regime.label}</span>
              </>
            )}
          </p>
        )}
        <Crossing file={file} />
      </>
    );
  }

  return (
    <section className="stack" style={{ gap: "var(--gap-sm)", marginTop: "var(--gap-xl)" }}>
      <div className="eyebrow">Options and regime</div>
      {(pc || regime) && (
      <div className="grid-auto">
        {pc && (
          <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="footnote muted">CBOE put/call, {day(pc.as_of)}</div>
            <div className="num" style={{ fontSize: "var(--size-h2)" }}>{ratio(pc.total)}</div>
            <div className="caption dim">
              Stocks {ratio(pc.equity)} · indexes {ratio(pc.index)} · SPX {ratio(pc.spx)}
            </div>
            <p className="caption dim" style={{ margin: 0 }}>
              Puts traded for every call. Higher means option buyers leaned
              toward protection that day.
            </p>
          </div>
        )}
        {regime && (
          <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="footnote muted">Market Desk regime, {day(regime.as_of)}</div>
            <div className="num" style={{ fontSize: "var(--size-h2)",
                                         color: REGIME_TONE[regime.label] }}>
              {regime.label}
            </div>
            <div className="caption dim">
              Score {regime.score > 0 ? "+" : ""}{regime.score}: one vote each,
              up, down or neutral, from the VIX curve, breadth, S&amp;P dealer
              gamma, credit, sector rotation and put/call, with an inverted
              yield curve counting only against.
            </div>
          </div>
        )}
      </div>
      )}
      <Crossing file={file} />
    </section>
  );
}
