import { BreadthBarcode } from "@/components/BreadthBarcode";
import { BreadthGrid } from "@/components/BreadthGrid";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { MarketContext } from "@/components/MarketContext";
import { longDate } from "@/lib/format";
import { getBarcode, getBreadth, getMarketContext, getMeta, hasData } from "@/lib/data";
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
      <div style={{ margin: "var(--pad-lg) 0 var(--pad-xl)" }}>
        <BreadthBarcode strip={getBarcode()} />
      </div>
      <BreadthGrid cards={breadth.cards} universe={breadth.universe_size} />
      <MarketContext file={getMarketContext()} />
      <MarketCTA />
    </div>
  );
}
