import Link from "next/link";
import { notFound } from "next/navigation";
import { DataBanner, NoData } from "@/components/DataBanner";
import { EditionView } from "@/components/EditionView";
import { getEdition, getEditions, getMeta, hasData } from "@/lib/data";

export function generateStaticParams() {
  return (getEditions()?.editions ?? []).map((row) => ({ date: row.date }));
}

export default async function EditionPage({ params }: { params: Promise<{ date: string }> }) {
  if (!hasData()) return <NoData />;
  const { date } = await params;
  const edition = getEdition(date);
  if (!edition) notFound();
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="caption" style={{ marginBottom: "var(--gap-sm)" }}>
        <Link href="/market/editions" style={{ textDecoration: "underline" }}>All back issues</Link>
      </div>
      <EditionView edition={edition} index={getEditions()} />
    </div>
  );
}
