import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { Scatter } from "@/components/Scatter";
import { copy } from "@/lib/copy";
import { getMeta, getRotation, hasData } from "@/lib/data";

export default function RotationPage() {
  if (!hasData()) return <NoData />;
  const rotation = getRotation();
  if (!rotation) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Rotation</h1>
      <p className="muted footnote">
        Strength now across the bottom, momentum {rotation.lookback_label} up the side.
        {" "}{copy("rotation.quadrants")}
      </p>
      <Scatter
        labels={rotation.quadrant_labels}
        groups={[
          { key: "industries", label: "Industries", points: rotation.industries.points,
            counts: rotation.industries.counts,
            hrefPrefix: "/industries/" },
          { key: "themes", label: "Themes", points: rotation.themes.points,
            counts: rotation.themes.counts, hrefPrefix: "/themes/" },
          { key: "stocks", label: "Stocks", points: rotation.stocks.points,
            counts: rotation.stocks.counts, hrefPrefix: "/stocks/" },
        ]}
      />
      <MarketCTA />
    </div>
  );
}
