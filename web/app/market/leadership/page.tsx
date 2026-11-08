import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import {
  LayerCountsGrid, LayerIndustries, LayerLists, LayerPath,
} from "@/components/Leadership";
import { getLeadership, getMeta, hasData } from "@/lib/data";
import Link from "next/link";

export default function LeadershipPage() {
  if (!hasData()) return <NoData />;
  const s = getLeadership();
  if (!s || !s.counts) return <NoData />;
  const ia = s.industries_aligned;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · stock against industry</div>
      <h1>Leadership layers</h1>
      <p className="muted footnote">
        Every stock at $3 or more, read against an equal-weighted index of its
        own industry over one, three and six months, with the industry read
        against the S&amp;P 500 the way the <Link href="/market/radar">strength
        radar</Link> reads its groups. {s.grouped.toLocaleString("en-US")} of{" "}
        {s.n.toLocaleString("en-US")} have an industry large enough to index.
        Of {ia.n} industries, {ia.full} are fully aligned against the S&amp;P
        500, {ia.partial} partly, and {ia.positive} are ahead of it over six
        months. A layer is where a stock sits, not a call on it.
      </p>

      <LayerCountsGrid s={s} />

      <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
        <h2>The strongest in each layer</h2>
        <p className="caption dim">
          Ranked by six months against the industry; turning by three months,
          since six is behind by definition; caution weakest first.
        </p>
        <LayerLists s={s} />
      </section>

      <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
        <h2>Where the front line comes from</h2>
        <LayerIndustries s={s} />
      </section>

      <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
        <h2>The week</h2>
        <LayerPath path={s.path} order={s.order} labels={s.labels} />
      </section>
      <MarketCTA />
    </div>
  );
}
