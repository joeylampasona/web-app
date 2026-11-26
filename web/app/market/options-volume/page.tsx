import type { Metadata } from "next";
import { DataBanner, NoData } from "@/components/DataBanner";
import { GatedOptionsVolumeBoard } from "@/components/GatedOptionsVolumeBoard";
import { MarketCTA } from "@/components/MarketCTA";
import { getMeta, getOptionsVolumeBoard, hasData } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const metadata: Metadata = {
  title: `Options volume — ${SITE_NAME}`,
  description: "Where the day's option trading was large against the open interest "
               + "already on the book, with calls against puts and the busiest contracts.",
};

export default function OptionsVolumePage() {
  if (!hasData()) return <NoData />;
  const board = getOptionsVolumeBoard();
  if (!board) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Options volume</h1>
      <p className="muted footnote">{board.copy.header}</p>
      <p className="caption dim">{board.copy.subhead}</p>

      {board.rows.length === 0 ? (
        <div className="card muted footnote" style={{ marginTop: "var(--gap-md)" }}>
          No name traded enough option contracts on this run to be ranked. We
          only read chains for names carrying a dated event, and most listed
          companies have no options at all.
        </div>
      ) : (
        <GatedOptionsVolumeBoard rows={board.rows} total={board.count} read={board.read}
                                 gated={Boolean(board.gated)}
                                 boardRows={board.board_rows} />
      )}

      <p className="caption dim" style={{ marginTop: "var(--pad-lg)" }}>{board.copy.footer}</p>
      <MarketCTA />
    </div>
  );
}
