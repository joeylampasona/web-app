import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DataBanner, NoData } from "@/components/DataBanner";
import { StockDetail } from "@/components/StockDetail";
import { getMeta, getStock, hasData } from "@/lib/data";

export const dynamicParams = true;

/**
 * A shared link should say which company it is in the title, not just in the
 * image — the title is what a text-only preview and a browser tab both show.
 */
export async function generateMetadata({ params }: {
  params: Promise<{ symbol: string }>;
}): Promise<Metadata> {
  const { symbol } = await params;
  const stock = getStock(symbol);
  if (!stock) return { title: `${symbol.toUpperCase()} — Base & Breakout` };

  const ranked = typeof stock.rs_rating === "number";
  const setup = stock.primary_setup;
  const description = [
    stock.industry,
    `RS ${ranked ? stock.rs_rating : "not ranked yet"}`,
    setup ? `${setup.screen.replace(/_/g, " ")}, ${setup.stage.replace(/_/g, " ")}`
          : "not on a screen right now",
  ].filter(Boolean).join(" · ");

  const title = `${stock.name} (${stock.symbol}) — Base & Breakout`;
  return {
    title,
    description,
    openGraph: { title, description },
    // card has to be repeated: a per-page twitter block replaces the layout's
    // rather than merging into it, and without it the preview drops to a small
    // square thumbnail instead of the wide image.
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function StockPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  if (!hasData()) return <NoData />;
  const { symbol } = await params;
  const stock = getStock(symbol);
  if (!stock) notFound();
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <StockDetail stock={stock} />
    </div>
  );
}
