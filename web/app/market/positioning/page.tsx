import type { Metadata } from "next";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { GatedPositioning } from "@/components/Positioning";
import { getMeta, getPositioning, hasData } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const metadata: Metadata = {
  title: `Positioning — ${SITE_NAME}`,
  description: "How hedge funds and speculators are positioned in futures, and how stretched it is.",
};

function weekOf(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "long", day: "numeric", timeZone: "UTC",
  });
}

export default function PositioningPage() {
  if (!hasData()) return <NoData />;
  const file = getPositioning();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Positioning</h1>
      <p className="muted footnote">
        How the fast money is positioned in futures, from the CFTC&apos;s weekly
        Commitments of Traders report: leveraged funds in the financial
        markets, large speculators in gold and oil. The percentile is the part
        to read. A position near the edge of its own history is crowded, and
        crowded positions are the ones that unwind fastest when the market
        turns against them.
      </p>

      {!file || file.markets.length === 0 ? (
        <div className="card muted footnote" style={{ marginTop: "var(--gap-md)" }}>
          No positioning report has arrived yet. It is published weekly, on Friday
          afternoons, for positions as of the Tuesday before.
        </div>
      ) : (
        <>
          <p className="caption dim">Positions as of Tuesday {weekOf(file.as_of)}.</p>
          <GatedPositioning file={file} />
        </>
      )}

      <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>
        Context, not a signal. Funds are often short index futures to hedge long
        stock books, so a net short is not a bet against the market on its own;
        the percentile against the same group&apos;s own history is what says
        whether it is unusual. Source: CFTC, via the Market Desk.
      </p>
      <MarketCTA />
    </div>
  );
}
