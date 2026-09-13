import { notFound } from "next/navigation";
import { DataBanner, NoData } from "@/components/DataBanner";
import { FreshnessPill } from "@/components/FreshnessPill";
import { ScreenBrowser } from "@/components/ScreenBrowser";
import { RS_NOTE } from "@/lib/copy";
import { SCREEN_KEYS, barsFor, getMeta, getScreen, hasData } from "@/lib/data";

export function generateStaticParams() {
  return SCREEN_KEYS.map((screen) => ({ screen }));
}

export default async function ScreenPage({
  params,
}: {
  params: Promise<{ screen: string }>;
}) {
  if (!hasData()) return <NoData />;
  const { screen } = await params;
  const file = getScreen(screen);
  if (!file) notFound();
  const meta = getMeta();
  const symbols = Object.values(file.setups).flat().map((s) => s.symbol);
  const bars = barsFor(symbols);

  return (
    <div className="page">
      <DataBanner meta={meta} />
      <div className="eyebrow">Screens · {file.name}</div>
      <FreshnessPill count={meta?.market_wide_breakouts ?? 0} asOf={file.as_of} />
      <ScreenBrowser file={file} bars={bars} />
      <p className="caption dim" style={{ marginTop: "var(--pad-xl)" }}>{RS_NOTE}</p>
    </div>
  );
}
