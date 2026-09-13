import { DataBanner, NoData } from "@/components/DataBanner";
import { FollowThroughPanel } from "@/components/FollowThroughPanel";
import { getFollowThrough, getMeta, hasData } from "@/lib/data";

export const metadata = {
  title: "Did it work? — Base & Breakout",
  description: "What happened to the breakouts each screen showed.",
};

export default function FollowThroughPage() {
  if (!hasData()) return <NoData />;
  const file = getFollowThrough();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · follow-through</div>
      <h1 style={{ marginBottom: "var(--gap-sm)" }}>Did it work?</h1>
      {file ? (
        <FollowThroughPanel file={file} />
      ) : (
        <p className="muted footnote">
          This build has no follow-through data yet. It is written by the nightly
          run, so it appears after the next one.
        </p>
      )}
    </div>
  );
}
