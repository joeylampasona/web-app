import { DataBanner, NoData } from "@/components/DataBanner";
import { SearchPanel } from "@/components/SearchPanel";
import {
  getBreakoutDates, getBreakouts, getMeta, getSearchIndex, hasData,
} from "@/lib/data";

export default function SearchPage() {
  if (!hasData()) return <NoData />;
  const meta = getMeta();
  const latest = getBreakoutDates()[0];
  const breakouts = latest ? getBreakouts(latest) : null;
  const suggestions = (breakouts?.setups ?? [])
    .slice(0, 10)
    .map((setup) => ({
      symbol: setup.symbol,
      name: setup.name,
      // Whether it is still above the level it cleared. A list of "recent
      // breakouts" with no state treats one that held and one that gave it all
      // back as the same event, and they are the two outcomes the page exists
      // to distinguish.
      holding: setup.now_vs_pivot_pct === null ? null : setup.now_vs_pivot_pct >= 0,
    }));

  return (
    <div className="page">
      <DataBanner meta={meta} />
      <div className="eyebrow">Search</div>
      <h1 style={{ marginBottom: "var(--gap-lg)" }}>Find a stock</h1>
      <SearchPanel
        rows={getSearchIndex()}
        suggestions={suggestions}
        themes={meta?.themes ?? []}
      />
    </div>
  );
}
