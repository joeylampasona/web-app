import { DataBanner, NoData } from "@/components/DataBanner";
import { LearnPanel } from "@/components/LearnPanel";
import { RS_NOTE } from "@/lib/copy";
import { getAllLearn, getMeta, hasData } from "@/lib/data";

export default function LearnPage() {
  if (!hasData()) return <NoData />;
  const files = getAllLearn();
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Learn · how it works</div>
      <h1 style={{ marginBottom: "var(--gap-lg)" }}>How the screens work</h1>
      <LearnPanel files={files} />
      <p className="caption dim" style={{ marginTop: "var(--pad-xl)" }}>{RS_NOTE}</p>
    </div>
  );
}
