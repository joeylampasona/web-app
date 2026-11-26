import Link from "next/link";
import type { CongressFile, CongressTrade } from "@/lib/types";
import { longDate } from "@/lib/format";

/**
 * Trades by members of the House, from the periodic transaction reports they
 * file with the Clerk.
 *
 * Read with three things in mind, and the page says all three. A member has
 * up to 45 days to report a trade, so the filed date is shown beside the
 * traded one with the gap between them. The amount is a band the form
 * offers, never a figure. And senators are not here at all: the Senate
 * publishes no file to read.
 *
 * Free to every reader and never gated. The statute that makes the reports
 * public allows their use by news media for dissemination to the general
 * public and for no other commercial purpose.
 */
const VERB: Record<string, string> = {
  buy: "Bought",
  sell: "Sold",
  "partial sale": "Sold part",
  exchange: "Exchanged",
};

const ACCOUNT: Record<string, string> = {
  self: "Own account",
  spouse: "Spouse",
  joint: "Joint",
  child: "Dependent child",
};

/** Whole days from the trade to the report, or null when either is missing. */
function gap(traded: string | null, filed: string | null): number | null {
  if (!traded || !filed) return null;
  const a = Date.parse(`${traded}T00:00:00Z`);
  const b = Date.parse(`${filed}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.round((b - a) / 86_400_000);
}

function Verb({ type }: { type: string }) {
  const tone = type === "buy" ? "gain" : type === "exchange" ? "" : "loss";
  return <span className={tone} style={{ fontWeight: 600 }}>{VERB[type] ?? type}</span>;
}

function Lag({ traded, filed }: { traded: string | null; filed: string | null }) {
  const days = gap(traded, filed);
  if (days == null) return null;
  // Past the 45 days the law allows, said plainly and without colour.
  return (
    <span className="caption dim">
      {" "}· {days} day{days === 1 ? "" : "s"} later{days > 45 ? ", past the 45 allowed" : ""}
    </span>
  );
}

function Rows({ trades, withSymbol }: {
  trades: (CongressTrade & { symbol?: string; name?: string })[];
  withSymbol: boolean;
}) {
  return (
    // Zero wide as far as its parents can tell, and then as wide as they
    // are: the stock page is a flex column inside the shell's grid, and a
    // table's own width would otherwise widen the whole page on a phone
    // instead of scrolling inside its card.
    <div className="scroll-x card" style={{ padding: 0, width: 0, minWidth: "100%" }}>
      <table className="data">
        <thead>
          <tr>
            {withSymbol && <th className="text">Ticker</th>}
            <th className="text">Member</th>
            <th className="text">Trade</th>
            <th className="text">Amount</th>
            <th className="text">Traded</th>
            <th className="text">Filed</th>
            <th className="text">Account</th>
            <th className="text">Report</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={`${t.url}-${t.symbol ?? ""}-${t.traded}-${t.type}-${i}`}>
              {withSymbol && (
                <td className="text">
                  <Link href={`/stocks/${t.symbol}`} className="mono"
                        style={{ fontWeight: 600, textDecoration: "underline" }}>
                    {t.symbol}
                  </Link>
                  {t.name && t.name !== t.symbol && <div className="caption dim">{t.name}</div>}
                </td>
              )}
              <td className="text" style={{ minWidth: 150 }}>
                {t.member}
                {t.district && <span className="caption dim"> · {t.district}</span>}
              </td>
              <td className="text"><Verb type={t.type} /></td>
              <td className="text num" style={{ whiteSpace: "nowrap" }}>{t.amount || "—"}</td>
              <td className="text" style={{ whiteSpace: "nowrap" }}>{longDate(t.traded)}</td>
              <td className="text" style={{ minWidth: 150 }}>
                {longDate(t.filed)}
                <Lag traded={t.traded} filed={t.filed} />
              </td>
              <td className="text">
                {t.owner ? (ACCOUNT[t.owner] ?? t.owner)
                  : <span className="dim" title="The report does not let the account be told reliably">Not stated</span>}
              </td>
              <td className="text">
                <a href={t.url} target="_blank" rel="noopener noreferrer"
                   style={{ textDecoration: "underline" }}>PDF</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const FOOTNOTE = "From periodic transaction reports filed with the Clerk of the House. "
  + "Members have up to 45 days to report a trade. Amounts are the bands the form "
  + "offers, not figures. Senators are not covered, and reports filed on paper are "
  + "not read. Not a signal.";

/** The card on a stock's own page. Nothing at all before the reports have
 *  ever been read; a plain "none" once they have and there are none. */
export function CongressCard({ trades }: { trades: CongressTrade[] | null | undefined }) {
  if (trades == null) return null;
  return (
    <section>
      <div className="eyebrow">Congress</div>
      {trades.length === 0 ? (
        <div className="card muted footnote">
          No member of the House has reported a trade in this stock in the last
          twelve months. Senators are not covered.
        </div>
      ) : (
        <div className="stack" style={{ gap: "var(--gap-sm)" }}>
          <Rows trades={trades} withSymbol={false} />
          <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>{FOOTNOTE}</p>
        </div>
      )}
    </section>
  );
}

/** The table on the Insider activity page: what was filed lately, across
 *  the names this site follows. */
export function CongressRecent({ file }: { file: CongressFile | null }) {
  if (!file) return null;
  const rows = file.rows ?? [];
  return (
    <section className="stack" id="congress"
             style={{ gap: "var(--gap-sm)", marginTop: "var(--pad-xl)" }}>
      <div className="eyebrow">Congress</div>
      <p className="muted footnote" style={{ margin: 0, maxWidth: "78ch" }}>
        {file.copy?.header ?? "Trades by members of the House of Representatives."}{" "}
        Filed in the last {file.days} days, newest report first.
      </p>
      {rows.length === 0 ? (
        <div className="card muted footnote">
          No report filed in the last {file.days} days names a stock this site follows.
        </div>
      ) : (
        <Rows trades={rows} withSymbol />
      )}
      <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>
        {file.copy?.footer ?? FOOTNOTE}
        {file.filings_read != null && (
          <> {file.filings_read.toLocaleString("en-US")} reports read
            {file.filings_unread ? <>, {file.filings_unread.toLocaleString("en-US")} filed on paper and not read</> : null}
            {file.newest_filed ? <>; the newest was filed {longDate(file.newest_filed)}</> : null}.</>
        )}
      </p>
    </section>
  );
}
