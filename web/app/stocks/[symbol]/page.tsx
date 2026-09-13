import { notFound } from "next/navigation";
import { DataBanner, NoData } from "@/components/DataBanner";
import { StockDetail } from "@/components/StockDetail";
import { getMeta, getStock, hasData } from "@/lib/data";

export const dynamicParams = true;

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
