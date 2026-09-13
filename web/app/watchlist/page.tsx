import { DataBanner, NoData } from "@/components/DataBanner";
import { WatchlistPanel, type WatchRow } from "@/components/WatchlistPanel";
import { getAllScreens, getMeta, getSearchIndex, hasData } from "@/lib/data";

export default function WatchlistPage() {
  if (!hasData()) return <NoData />;
  const byScreen = getAllScreens();
  const stages = new Map<string, { stage: string; within7: boolean; days: number | null }>();
  for (const file of byScreen) {
    for (const setups of Object.values(file.setups)) {
      for (const setup of setups) {
        if (!stages.has(setup.symbol)) {
          stages.set(setup.symbol, {
            stage: setup.stage,
            within7: Boolean(setup.catalysts?.earnings_within_7d),
            days: setup.catalysts?.days_until_earnings ?? null,
          });
        }
      }
    }
  }
  const rows: WatchRow[] = getSearchIndex().map((row) => ({
    symbol: row.symbol,
    name: row.name,
    rs_rating: row.rs_rating,
    stage: stages.get(row.symbol)?.stage ?? null,
    earnings_within_7d: stages.get(row.symbol)?.within7 ?? false,
    days_until_earnings: stages.get(row.symbol)?.days ?? null,
  }));

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Watchlist</div>
      <h1 style={{ marginBottom: "var(--gap-lg)" }}>Your watchlist</h1>
      <WatchlistPanel rows={rows} />
    </div>
  );
}
