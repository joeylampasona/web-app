import { notFound } from "next/navigation";
import { DataBanner, NoData } from "@/components/DataBanner";
import { GroupDetail } from "@/components/GroupDetail";
import { getGroup, getMeta, hasData, listGroups } from "@/lib/data";

export function generateStaticParams() {
  return listGroups("themes").map((slug) => ({ slug }));
}

export default async function ThemePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  if (!hasData()) return <NoData />;
  const { slug } = await params;
  const group = getGroup("themes", slug);
  if (!group) notFound();
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Theme</div>
      <h1 style={{ marginBottom: "var(--gap-lg)" }}>{group.name}</h1>
      <GroupDetail group={group} />
    </div>
  );
}
