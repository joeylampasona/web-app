import type { OptionsVolume as Volume, OptionsVolumeContract } from "@/lib/types";
import { CarriedOver, shortDay } from "./CarriedOver";

/**
 * One company's option trading for a session.
 *
 * Counted off the chain the nightly already reads for gamma, and only where
 * a contract traded on the chain's latest session: the source shows the
 * volume of the last day a contract traded, and for a thin one that can be
 * weeks back.
 *
 * Kept apart from the Market Desk's options read above it. That card is the
 * desk's summary of about seventy chains; this is this site's own count, for
 * every name whose chain it read. Where both give puts against calls they
 * can differ, because the desk counts every contract the source lists.
 *
 * It says what traded. It does not say who bought, whether a position was
 * opened or closed, or whether a busy strike is one leg of a spread, and the
 * card says so rather than leaving a reader to supply the story.
 */
export const UNUSUAL_RULE = "Traded at least twice its open interest, and at least 500 contracts.";
export const THIN_BOOK = "Open interest here is one source's own, which is missing for "
  + "much of the book, because the clearing house's figures were unavailable. "
  + "The share of open interest is overstated.";

export function contract(c: OptionsVolumeContract): string {
  const strike = c.strike.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return `${shortDay(c.expiry) ?? c.expiry} ${strike} ${c.side}`;
}

export function share(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`;
}

export function OptionsVolume({ volume }: { volume: Volume | null }) {
  if (!volume) return null;
  const session = shortDay(volume.session);
  const thin = volume.oi_source !== "occ";

  if (volume.volume <= 0) {
    return (
      <div className="card">
        <p className="footnote muted" style={{ margin: 0 }}>
          No option contract traded{session ? ` on ${session}` : " on the chain's latest session"},
          against {volume.open_interest.toLocaleString()} open.
        </p>
      </div>
    );
  }

  return (
    <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
      {volume.stale && (
        <p className="footnote book-note" style={{ margin: 0 }}>
          <CarriedOver title="The chain did not answer on this run. The figures are the last night's that did.">
            {shortDay(volume.as_of) ? `Read ${shortDay(volume.as_of)}` : "Earlier read"}
          </CarriedOver>{" "}
          This is an earlier night&rsquo;s count, kept because the chain was not read on this one.
        </p>
      )}
      <p className="footnote" style={{ margin: 0 }}>
        <strong className="num">{volume.volume.toLocaleString()}</strong> contracts
        traded{session ? ` on ${session}` : ""}:{" "}
        <strong className="num">{volume.call_volume.toLocaleString()}</strong> calls and{" "}
        <strong className="num">{volume.put_volume.toLocaleString()}</strong> puts
        {volume.put_call != null && (
          <>, <span className="num">{volume.put_call.toFixed(2)}</span> puts for every call</>
        )}.
      </p>
      {volume.volume_oi != null && (
        <p className="footnote" style={{ margin: 0 }}>
          That is <strong className="num">{share(volume.volume_oi)}</strong> of the{" "}
          <span className="num">{volume.open_interest.toLocaleString()}</span> contracts
          open across the {volume.expiries} expiries read
          {thin && <>{" "}<CarriedOver title={THIN_BOOK}>Partial book</CarriedOver></>}.
          {volume.vs_usual != null && volume.usual_volume != null ? (
            <>{" "}Against this name&rsquo;s own usual it is{" "}
              <strong className="num">{volume.vs_usual.toFixed(1)}×</strong>: the mean of
              its {volume.usual_sessions} earlier stored sessions
              is <span className="num">{volume.usual_volume.toLocaleString()}</span>.</>
          ) : (
            <span className="dim">{" "}What is usual for this name follows after five stored
              sessions{volume.usual_sessions ? ` (${volume.usual_sessions} so far)` : ""}.</span>
          )}
        </p>
      )}

      {volume.top.length > 0 && (
        <div className="scroll-x" style={{ marginTop: "var(--gap-xs)" }}>
          <table className="data">
            <thead>
              <tr>
                <th>Busiest contracts</th>
                <th>Traded</th>
                <th>Open</th>
                <th>Multiple</th>
              </tr>
            </thead>
            <tbody>
              {volume.top.map((c) => (
                <tr key={`${c.expiry}-${c.side}-${c.strike}`}>
                  <td className="text" style={{ whiteSpace: "nowrap" }}>
                    {contract(c)}
                    {c.unusual && (
                      <>{" "}<CarriedOver title={UNUSUAL_RULE}>Unusual</CarriedOver></>
                    )}
                  </td>
                  <td className="num">{c.volume.toLocaleString()}</td>
                  <td className="num">{c.open_interest.toLocaleString()}</td>
                  <td className="num">{c.multiple == null ? "—" : `${c.multiple.toFixed(1)}×`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="caption dim" style={{ margin: 0 }}>
        {volume.unusual > 0
          ? `${volume.unusual} contract${volume.unusual === 1 ? "" : "s"} traded at least twice
             ${volume.unusual === 1 ? "its" : "their"} open interest and at least 500 contracts. `
          : "No contract traded at least twice its open interest and at least 500 contracts. "}
        Volume says contracts changed hands, not who bought or why, and a busy
        strike may be one leg of a spread. Open interest is published once a
        day and predates the session. Not a signal.
      </p>
    </div>
  );
}
