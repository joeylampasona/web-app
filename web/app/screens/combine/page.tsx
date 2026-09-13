import { CombinePanel } from "@/components/CombinePanel";
import { DataBanner, NoData } from "@/components/DataBanner";
import { EAGER_CHARTS, barsFor, getAllScreens, getMeta, hasData } from "@/lib/data";

export default function CombinePage() {
  if (!hasData()) return <NoData />;
  const files = getAllScreens();
  const symbols = files.flatMap((file) =>
    Object.values(file.setups).flat().map((setup) => setup.symbol));
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Screens · combine</div>
      <h1 style={{ marginBottom: "var(--gap-lg)" }}>Combine screens</h1>
      <CombinePanel files={files} bars={barsFor([...new Set(symbols)].slice(0, EAGER_CHARTS))} />
    </div>
  );
}
