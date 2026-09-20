import type { Metadata } from "next";
import { DataBanner, NoData } from "@/components/DataBanner";
import { GatedGammaBoard } from "@/components/GatedGammaBoard";
import { MarketCTA } from "@/components/MarketCTA";
import { getGammaBoard, getMeta, hasData } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const metadata: Metadata = {
  title: `Gamma concentration — ${SITE_NAME}`,
  description: "Where open interest concentrates option gamma, for the names with "
               + "the deepest option books.",
};

export default function GammaPage() {
  if (!hasData()) return <NoData />;
  const board = getGammaBoard();
  if (!board) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Gamma concentration</h1>
      <p className="muted footnote">{board.copy.header}</p>
      <p className="caption dim">{board.copy.subhead}</p>

      {board.rows.length === 0 ? (
        <div className="card muted footnote" style={{ marginTop: "var(--gap-md)" }}>
          No name returned usable option open interest on this run. Most listed
          companies have no options at all, and we only read chains for names
          carrying a dated event.
        </div>
      ) : (
        <GatedGammaBoard rows={board.rows} total={board.count}
                         gated={Boolean(board.gated)} />
      )}

      <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>{board.copy.footer}</p>
      <MarketCTA />
    </div>
  );
}
