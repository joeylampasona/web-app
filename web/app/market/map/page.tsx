import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { Treemap } from "@/components/Treemap";
import { getMeta, getTreemap, hasData } from "@/lib/data";

export default function MapPage() {
  if (!hasData()) return <NoData />;
  const treemap = getTreemap();
  if (!treemap) return <NoData />;
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>The map</h1>
      <p className="muted footnote">
        Every industry with ten or more names, sized by the combined market value of its
        members. The badge counts fresh breakouts inside it. Tap to drill in.
      </p>
      <Treemap tiles={treemap.tiles} />
      <MarketCTA />
    </div>
  );
}
