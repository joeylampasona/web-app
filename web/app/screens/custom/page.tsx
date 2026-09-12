import { CustomScreenPanel } from "@/components/CustomScreenPanel";
import { DataBanner, NoData } from "@/components/DataBanner";
import { barsFor, getAllLearn, getAllScreens, getMeta, hasData } from "@/lib/data";

export default function CustomScreenPage() {
  if (!hasData()) return <NoData />;
  const files = getAllScreens();
  const symbols = files.flatMap((file) =>
    Object.values(file.setups).flat().map((setup) => setup.symbol));
  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Screens · create your own</div>
      <h1 style={{ marginBottom: "var(--gap-sm)" }}>Move the dials yourself</h1>
      <p className="muted footnote">
        Every dial below is generated from the same schema the detectors read, so what
        you see here is exactly what the code checks.
      </p>
      <CustomScreenPanel learn={getAllLearn()} files={files}
                         bars={barsFor([...new Set(symbols)])} />
    </div>
  );
}
