import { notFound } from "next/navigation";
import { DataBanner, NoData } from "@/components/DataBanner";
import { ScreenGlyph, glyphLabel } from "@/components/ScreenGlyph";
import { GatedScreenBrowser } from "@/components/GatedScreenBrowser";
import { WhatChanged } from "@/components/WhatChanged";
import { RS_NOTE } from "@/lib/copy";
import { longDate } from "@/lib/format";
import { screenClass } from "@/lib/screenColour";
import { EAGER_CHARTS, SCREEN_KEYS, barsFor, getDiff, getMeta, getScreen, hasData } from "@/lib/data";
import { screenCard } from "@/lib/cards/cards";
import { cardMetadata } from "@/lib/cards/metadata";
import { PageShare } from "@/lib/cards/share";

export function generateStaticParams() {
  return SCREEN_KEYS.map((screen) => ({ screen }));
}

export async function generateMetadata({ params }: { params: Promise<{ screen: string }> }) {
  const { screen } = await params;
  const file = getScreen(screen);
  if (!file) return {};
  return cardMetadata({
    title: file.name,
    description: file.description,
    card: `/share/screen/${screen}.png`,
    version: file.as_of,
  });
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
      {/* The screen's own masthead: its name as a headline, what it looks
          for as the deck, and its shape drawn large enough to read as one. */}
      <header className="screen-head">
        <div className="stack" style={{ gap: "var(--gap-md)", minWidth: 0 }}>
          <div className="kicker">
            Screen · {file.total.toLocaleString("en-US")} names · updated {longDate(file.as_of)}
          </div>
          <h1 className="passport-name">{file.name}</h1>
          <p style={{ margin: 0, maxWidth: "64ch", color: "var(--text-secondary)" }}>
            {file.description}
          </p>
          <div className="caption dim">
            {meta?.market_wide_breakouts ?? 0} names broke out market-wide on this session.
          </div>
          <PageShare card={screenCard(screen)} image={`/share/screen/${screen}.png`}
                     title={file.name} />
        </div>
        <figure className={`screen-figure ${screenClass(screen)}`}>
          <ScreenGlyph href={`/screens/${screen}`} size={132} />
          <figcaption className="caption dim">{glyphLabel(`/screens/${screen}`)}</figcaption>
        </figure>
      </header>
      <WhatChanged
        diff={diff}
        screenName={file.name}
        direction={file.direction}
        href={file.has_followthrough === false ? undefined : "/market/followthrough"}
      />
      <GatedScreenBrowser file={file} bars={bars} describe={false} />
      <p className="caption dim" style={{ marginTop: "var(--pad-xl)" }}>{RS_NOTE}</p>
    </div>
  );
}
