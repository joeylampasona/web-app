import { BreadthGrid } from "@/components/BreadthGrid";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { longDate } from "@/lib/format";
import { getBreadth, getMeta, hasData } from "@/lib/data";

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
      <p className="muted footnote">
        How much of the {breadth.universe_size.toLocaleString()}-name universe is taking
        part, as of {longDate(breadth.as_of)}. These are counts of what happened, not
        signals about what happens next.
      </p>
      <BreadthGrid cards={breadth.cards} universe={breadth.universe_size} />
      <MarketCTA />
    </div>
  );
}
