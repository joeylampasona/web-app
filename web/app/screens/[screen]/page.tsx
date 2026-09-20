import { notFound } from "next/navigation";
import { DataBanner, NoData } from "@/components/DataBanner";
import { FreshnessPill } from "@/components/FreshnessPill";
import { GatedScreenBrowser } from "@/components/GatedScreenBrowser";
import { WhatChanged } from "@/components/WhatChanged";
import { RS_NOTE } from "@/lib/copy";
import { EAGER_CHARTS, SCREEN_KEYS, barsFor, getDiff, getMeta, getScreen, hasData } from "@/lib/data";

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
  const bars = barsFor(symbols.slice(0, EAGER_CHARTS));
  const diff = getDiff()?.screens?.[screen];

  return (
    <div className="page">
      <DataBanner meta={meta} />
      <div className="eyebrow">Screens · {file.name}</div>
      <FreshnessPill count={meta?.market_wide_breakouts ?? 0} asOf={file.as_of} />
      <WhatChanged
        diff={diff}
        screenName={file.name}
        direction={file.direction}
        href={file.has_followthrough === false ? undefined : "/market/followthrough"}
      />
      <GatedScreenBrowser file={file} bars={bars} />
      <p className="caption dim" style={{ marginTop: "var(--pad-xl)" }}>{RS_NOTE}</p>
    </div>
  );
}
