import type { Metadata } from "next";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { GatedSeasonalGrid } from "@/components/GatedSeasonalGrid";
import { getSeasonals, getMeta, hasData } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const metadata: Metadata = {
  title: `Seasonals — ${SITE_NAME}`,
  description: "What each month actually did, year by year, for the benchmark and sectors.",
};

export default function SeasonalsPage() {
  if (!hasData()) return <NoData />;
  const file = getSeasonals();
  if (!file) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Seasonals</h1>
      <p className="muted footnote">{file.copy.header}</p>
      <p className="caption dim">{file.copy.subhead}</p>

      {file.symbols.length === 0 ? (
        <div className="card muted footnote" style={{ marginTop: "var(--gap-md)" }}>
          Not enough history to build a grid on this run.
        </div>
      ) : (
        <GatedSeasonalGrid symbols={file.symbols}
                           total={file.count ?? file.symbols.length}
                           gated={Boolean(file.gated)} />
      )}

      <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>{file.copy.footer}</p>
      <MarketCTA />
    </div>
  );
}
