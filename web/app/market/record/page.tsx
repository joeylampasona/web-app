import { DataBanner, NoData } from "@/components/DataBanner";
import { ScreenRecord } from "@/components/ScreenRecord";
import { getMeta, getScreenRecord, hasData } from "@/lib/data";

export const metadata = {
  title: "The record",
  description: "Each screen's breakouts counted, and which screens are on watch.",
};

export default function RecordPage() {
  if (!hasData()) return <NoData />;
  const file = getScreenRecord();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the record</div>
      <h1 style={{ marginBottom: "var(--gap-sm)" }}>The record</h1>
      <p style={{ margin: "0 0 var(--pad-lg)", maxWidth: "64ch", color: "var(--text-secondary)" }}>
        What each screen&rsquo;s breakouts did next, counted, and what happens to a
        screen whose breakouts stop paying.
      </p>
      {file ? (
        <ScreenRecord file={file} />
      ) : (
        <p className="muted footnote">
          This build has no record yet. It is counted by the nightly run, so it
          appears after the next one.
        </p>
      )}
    </div>
  );
}
