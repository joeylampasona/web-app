import { money } from "@/lib/format";
import type { InsiderSummary } from "@/lib/types";

/**
 * What the people who run the company did with their own shares.
 *
 * Form 4 is filed under penalty of perjury within two business days, which
 * makes it better evidence than most of what this site ingests. But the number
 * everyone quotes is usually wrong, because it counts things nobody chose:
 *
 *   P  bought on the open market      a decision
 *   S  sold on the open market        a decision
 *   A  granted shares                 the company's vesting schedule
 *   M  exercised options              converting what they already held
 *   F  shares withheld for tax        automatic on vesting
 *   G  gift
 *
 * Most "insider selling" headlines are F — tax withholding on a vesting date
 * set years earlier. So the decisions are the headline here and the mechanics
 * are counted beside them, never added to them.
 */
export function InsiderPanel({ insiders }: { insiders: InsiderSummary | null }) {
  if (!insiders) {
    return (
      <p className="muted footnote">
        No Form 4 filings read for this company in the last six months. That can
        mean nobody filed, or that this name has not been on a screen long enough
        for us to have fetched them.
      </p>
    );
  }

  const { buys, sells, mechanics, buyers, sellers, recent } = insiders;
  const months = Math.round(insiders.window_days / 30);
  const quiet = buys === 0 && sells === 0;

  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      {quiet ? (
        <p className="muted footnote" style={{ margin: 0 }}>
          Nobody bought or sold on the open market in the last {months} months.
          {mechanics > 0 && ` There ${mechanics === 1 ? "was" : "were"} ${mechanics} `
            + `${mechanics === 1 ? "filing" : "filings"} for awards, option exercises `
            + `or shares withheld to pay tax — those happen on a vesting schedule, `
            + `so they are not a decision to buy or sell.`}
        </p>
      ) : (
        <>
          <div className="grid-2">
            <div className="card">
              <div className="footnote muted">Bought on the open market</div>
              <div className="num" style={{ fontSize: "var(--size-h2)" }}>{buys}</div>
              {insiders.buy_value > 0 && (
                <div className="caption dim">{money(insiders.buy_value)} total</div>
              )}
            </div>
            <div className="card">
              <div className="footnote muted">Sold on the open market</div>
              <div className="num" style={{ fontSize: "var(--size-h2)" }}>{sells}</div>
              {insiders.sell_value > 0 && (
                <div className="caption dim">{money(insiders.sell_value)} total</div>
              )}
            </div>
          </div>
          {(buyers.length > 0 || sellers.length > 0) && (
            <p className="caption dim" style={{ margin: 0 }}>
              {buyers.length > 0 && `Bought: ${buyers.join(", ")}. `}
              {sellers.length > 0 && `Sold: ${sellers.join(", ")}.`}
            </p>
          )}
        </>
      )}

      {mechanics > 0 && !quiet && (
        <p className="caption dim" style={{ margin: 0 }}>
          Not counted above: {mechanics} {mechanics === 1 ? "filing" : "filings"} for
          awards, option exercises, gifts or shares withheld to pay tax. Those follow a
          vesting schedule nobody chose the timing of, and counting them as selling is
          how that number gets misread.
        </p>
      )}

      {recent.length > 0 && (
        <div className="stack" style={{ gap: "var(--gap-xs)", marginTop: "var(--gap-xs)" }}>
          <div className="eyebrow">Most recent filings</div>
          {recent.map((t, i) => (
            <div key={`${t.traded_at}-${t.owner}-${i}`} className="between footnote"
                 style={{ gap: "var(--gap-sm)" }}>
              <span className="grow">
                <span className="mono">{t.traded_at}</span>{" "}
                <span>{t.owner}</span>{" "}
                <span className="dim">· {t.role}</span>
              </span>
              <span className="row" style={{ gap: "var(--gap-xs)" }}>
                <span className={t.decision ? "" : "dim"}>{t.what}</span>
                {t.shares !== null && (
                  <span className="num dim">{Math.round(t.shares).toLocaleString()}</span>
                )}
                {t.value !== null && <span className="num">{money(t.value)}</span>}
              </span>
            </div>
          ))}
        </div>
      )}

      <p className="caption dim" style={{ margin: 0 }}>
        From SEC Form 4, filed within two business days of the trade. What was
        filed, not what it means.
      </p>
    </div>
  );
}
