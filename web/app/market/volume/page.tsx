import type { Metadata } from "next";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { VolumeHeat } from "@/components/VolumeHeat";
import { getVolumeHeat, getMeta, hasData } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const metadata: Metadata = {
  title: `Relative volume — ${SITE_NAME}`,
  description: "Which names traded unusually heavily in the session that just closed.",
};

export default function VolumePage() {
  if (!hasData()) return <NoData />;
  const file = getVolumeHeat();
  if (!file) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Relative volume</h1>
      <p className="muted footnote">{file.copy.header}</p>
      <p className="caption dim">{file.copy.subhead}</p>

      {file.rows.length === 0 ? (
        <div className="card muted footnote" style={{ marginTop: "var(--gap-md)" }}>
          No volume readings on this run.
        </div>
      ) : (
        <VolumeHeat rows={file.rows} total={file.count} bands={file.bands} />
      )}

      <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>{file.copy.footer}</p>
      <MarketCTA />
    </div>
  );
}
