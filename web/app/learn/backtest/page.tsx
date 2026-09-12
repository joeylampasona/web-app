import { DataBanner, NoData } from "@/components/DataBanner";
import { BacktestPanel } from "@/components/BacktestPanel";
import { getBacktestOptions, getDefaultBacktest, getMeta, hasData } from "@/lib/data";

export default function BacktestPage() {
  if (!hasData()) return <NoData />;
  const options = getBacktestOptions();
  if (!options) return <NoData />;
  const initial = getDefaultBacktest(String(options.defaults.screen ?? "vcp"));

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Learn · backtest</div>
      <h1 style={{ marginBottom: "var(--gap-sm)" }}>Test the rules yourself</h1>
      <p className="muted footnote">
        The default combination for each screen is precomputed so this page loads
        instantly. Change anything and the run happens on demand. Losing trades are
        published alongside the winners — that is the point of the page.
      </p>
      <BacktestPanel
        options={options.options}
        defaults={options.defaults as Record<string, string | number | boolean>}
        years={options.years}
        initial={initial}
      />
    </div>
  );
}
