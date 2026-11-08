import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { RadarBreadth, RadarGroups, RadarMap, RadarPairs, RadarRead } from "@/components/Radar";
import { LayerCountsGrid } from "@/components/Leadership";
import { getLeadership, getMeta, getRadar, hasData } from "@/lib/data";
import Link from "next/link";

export default function RadarPage() {
  if (!hasData()) return <NoData />;
  const radar = getRadar();
  if (!radar) return <NoData />;
  const layers = getLeadership();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · where strength sits</div>
      <h1>Strength radar</h1>
      <p className="muted footnote">
        Price ratios read over one, two, three, six and twelve months: growth
        against the market, small caps against growth and the market, equal
        weight against cap weight, and {radar.groups.length} sector and group
        funds against the S&amp;P 500. A ratio is aligned when its own averages
        are stacked upward. Measured from closing prices; nothing here is a
        forecast.
      </p>

      <RadarRead radar={radar} />

      <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
        <h2>The key relationships</h2>
        <RadarPairs radar={radar} />
      </section>

      <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
        <h2>The map</h2>
        <RadarMap radar={radar} />
      </section>

      <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
        <h2>Breadth across the groups</h2>
        <p className="caption dim">
          How many of the {radar.breadth.at(-1)?.n ?? 0} groups are aligned, and
          how many are ahead of the S&amp;P 500, session by session this week.
        </p>
        <RadarBreadth radar={radar} />
      </section>

      {layers?.counts && (
        <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
          <h2>The stocks underneath</h2>
          <p className="caption dim">
            {layers.n.toLocaleString("en-US")} stocks, each read against its own
            industry. The names in each layer are on{" "}
            <Link href="/market/leadership">leadership layers</Link>.
          </p>
          <LayerCountsGrid s={layers} />
        </section>
      )}

      <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
        <h2>Every group</h2>
        <RadarGroups radar={radar} />
      </section>
      <MarketCTA />
    </div>
  );
}
