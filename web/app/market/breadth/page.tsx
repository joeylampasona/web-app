import { BreadthBarcode } from "@/components/BreadthBarcode";
import { BreadthGrid } from "@/components/BreadthGrid";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { MarketContext } from "@/components/MarketContext";
import { longDate } from "@/lib/format";
import { getBarcode, getBreadth, getIndexes, getMarketContext, getMeta, hasData } from "@/lib/data";
import { breadthCard } from "@/lib/cards/cards";
import { cardMetadata } from "@/lib/cards/metadata";
import { PageShare } from "@/lib/cards/share";

export function generateMetadata() {
  return cardMetadata({
    title: "Breadth",
    description: "How much of the market is taking part: counts of what happened at the close.",
    card: "/share/breadth.png",
    version: getMeta()?.as_of,
  });
}

export default function BreadthPage() {
  if (!hasData()) return <NoData />;
  const breadth = getBreadth();
  const meta = getMeta();
  if (!breadth) return <NoData />;
  // One sentence, and only on a night the indexes disagree at an extreme.
  const divergence = getIndexes()?.divergence ?? null;

  return (
    <div className="page">
      <DataBanner meta={meta} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Breadth</h1>
      <PageShare card={breadthCard()} image="/share/breadth.png" title="Breadth" />
      <p className="muted footnote">
        How much of the {breadth.universe_size.toLocaleString()}-name universe is taking
        part, as of {longDate(breadth.as_of)}. These are counts of what happened, not
        signals about what happens next.
      </p>
      {divergence && (
        <div className="card" style={{ margin: "var(--pad-lg) 0 0",
                                       padding: "var(--pad-sm) var(--pad-md)",
                                       borderLeft: "3px solid var(--warn)" }}>
          <div className="caption muted">The indexes disagree</div>
          <p style={{ margin: "2px 0 0" }}>{divergence.sentence}</p>
          <p className="caption dim" style={{ margin: "4px 0 0" }}>
            Closing prices over the last {divergence.window} sessions. It says
            they have parted, not which of them is right.
          </p>
        </div>
      )}
      <div style={{ margin: "var(--pad-lg) 0 var(--pad-xl)" }}>
        <BreadthBarcode strip={getBarcode()} />
      </div>
      <BreadthGrid cards={breadth.cards} universe={breadth.universe_size} />
      <MarketContext file={getMarketContext()} />
      <MarketCTA />
    </div>
  );
}
