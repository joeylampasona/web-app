import { notFound } from "next/navigation";
import { DataBanner, NoData } from "@/components/DataBanner";
import { GroupDetail } from "@/components/GroupDetail";
import { getGroup, getMeta, hasData, listGroups } from "@/lib/data";

export function generateStaticParams() {
  return listGroups("industries").map((slug) => ({ slug }));
}

export default async function IndustryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  if (!hasData()) return <NoData />;
  const { slug } = await params;
  const group = getGroup("industries", slug);
  if (!group) notFound();
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Industry</div>
      <h1 style={{ marginBottom: "var(--gap-lg)" }}>{group.name}</h1>
      <GroupDetail group={group} />
    </div>
  );
}
