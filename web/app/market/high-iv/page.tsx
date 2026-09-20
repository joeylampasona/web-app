import { DataBanner, NoData } from "@/components/DataBanner";
import { HighIVBrowser } from "@/components/HighIVBrowser";
import { MarketCTA } from "@/components/MarketCTA";
import { getHighIV, getMeta, hasData } from "@/lib/data";

export default function HighIVPage() {
  if (!hasData()) return <NoData />;
  const iv = getHighIV();
  if (!iv) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>High IV</h1>
      <p className="muted footnote">{iv.copy.header}</p>
      <p className="caption dim">{iv.copy.subhead}</p>

      {iv.rows.length === 0 ? (
        <div className="card muted footnote" style={{ marginTop: "var(--gap-md)" }}>
          No names qualify right now. A ticker only appears here when it has a dated
          event of its own and listed options against it.
        </div>
      ) : (
        <HighIVBrowser rows={iv.rows} dots={iv.dots} bandLabels={iv.band_labels} />
      )}

      <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>{iv.copy.footer}</p>
      <MarketCTA />
    </div>
  );
}
