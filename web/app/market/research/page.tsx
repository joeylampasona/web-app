import Link from "next/link";
import { DataBanner, NoData } from "@/components/DataBanner";
import { Ledger } from "@/components/Ledger";
import { getLedger, getMeta, hasData } from "@/lib/data";

export const metadata = {
  title: "What we tested",
  description: "Every question this site has put to real data, with the failures kept.",
};

export default function ResearchPage() {
  if (!hasData()) return <NoData />;
  const file = getLedger();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the ledger</div>
      <h1 style={{ marginBottom: "var(--gap-sm)" }}>What we tested</h1>
      <p style={{ margin: "0 0 var(--pad-lg)", maxWidth: "64ch", color: "var(--text-secondary)" }}>
        Every question put to real data, what was measured, and how it came out.
        The ones that came out against the idea are kept, and so are the ones
        still waiting on data that does not exist yet. For how the screens
        themselves have done, see{" "}
        <Link href="/market/record" style={{ color: "var(--link)", textDecoration: "underline" }}>
          the record
        </Link>.
      </p>
      {file ? (
        <Ledger file={file} />
      ) : (
        <p className="muted footnote">
          This build has no ledger yet. It is copied in by the nightly run, so it
          appears after the next one.
        </p>
      )}
    </div>
  );
}
