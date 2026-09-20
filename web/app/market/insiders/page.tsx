import type { Metadata } from "next";
import { DataBanner, NoData } from "@/components/DataBanner";
import { InsiderCalendar } from "@/components/InsiderCalendar";
import { MarketCTA } from "@/components/MarketCTA";
import { getInsiderCalendar, getMeta, hasData } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const metadata: Metadata = {
  title: `Insider activity — ${SITE_NAME}`,
  description: "Open-market purchases and sales by officers, directors and 10% owners.",
};

export default function InsidersPage() {
  if (!hasData()) return <NoData />;
  const file = getInsiderCalendar();
  if (!file) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Insider activity</h1>
      <p className="muted footnote">{file.copy.header}</p>
      <p className="caption dim">{file.copy.subhead}</p>

      {file.days.length === 0 ? (
        <div className="card muted footnote" style={{ marginTop: "var(--gap-md)" }}>
          No open-market purchases or sales filed in this window. That is a normal
          reading — most Form 4s are grants and tax withholding, which are left out
          of this page on purpose.
        </div>
      ) : (
        <InsiderCalendar days={file.days} />
      )}

      <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>{file.copy.footer}</p>
      <MarketCTA />
    </div>
  );
}
