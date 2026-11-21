import { DataBanner, NoData } from "@/components/DataBanner";
import { FollowThroughPanel } from "@/components/FollowThroughPanel";
import { getFollowThrough, getMeta, hasData } from "@/lib/data";
import { followCard } from "@/lib/cards/cards";
import { cardMetadata } from "@/lib/cards/metadata";
import { PageShare } from "@/lib/cards/share";

export function generateMetadata() {
  return cardMetadata({
    title: "Did it work?",
    description: "What happened to the breakouts each screen showed.",
    card: "/share/followthrough.png",
    version: getMeta()?.as_of,
  });
}

export default function FollowThroughPage() {
  if (!hasData()) return <NoData />;
  const file = getFollowThrough();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · follow-through</div>
      <h1 style={{ marginBottom: "var(--gap-sm)" }}>Did it work?</h1>
      <PageShare card={followCard()} image="/share/followthrough.png" title="Did it work?" />
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
