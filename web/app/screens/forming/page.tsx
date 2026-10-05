import type { Metadata } from "next";
import { DataBanner, NoData } from "@/components/DataBanner";
import { FormingAll } from "@/components/FormingBrowser";
import { RS_NOTE, SITE_NAME } from "@/lib/copy";
import { getFormingSummary, getMeta, hasData } from "@/lib/data";

export const metadata: Metadata = {
  title: `Forming, every screen — ${SITE_NAME}`,
  description: "Every base forming across every screen, in one list.",
};

export default function FormingPage() {
  if (!hasData()) return <NoData />;
  const summary = getFormingSummary();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Screens · forming, all of them</div>
      <h1>Forming</h1>
      <p className="muted footnote">
        Every base that has not broken yet, from every screen, one row per stock.
        A stock forming on several screens at once shows them all — more than one
        reading of the same structure is worth knowing about.
      </p>
      {!summary ? (
        <div className="card muted footnote">
          The combined list arrives with the next nightly run.
        </div>
      ) : (
        <FormingAll summary={summary} />
      )}
      <p className="caption dim" style={{ marginTop: "var(--pad-xl)" }}>{RS_NOTE}</p>
    </div>
  );
}
