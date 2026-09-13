import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { HeatTable, StrengthTable } from "@/components/SectorStrength";
import { PriceChange } from "@/components/PriceChange";
import { getMeta, getSectors, hasData } from "@/lib/data";

export default function SectorsPage() {
  if (!hasData()) return <NoData />;
  const sectors = getSectors();
  if (!sectors) return <NoData />;

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>Sector strength</h1>
      <p className="muted footnote">
        Groups are ranked against each other on the same 1-99 scale their members use.
        Only groups with ten or more names appear.
      </p>

      <StrengthTable strong={sectors.strongest} weak={sectors.weakest} kind="industries" />
      <HeatTable heating={sectors.heating_cooling.heating}
                 cooling={sectors.heating_cooling.cooling} kind="industries" />

      <div style={{ marginTop: "var(--pad-xl)" }}>
        <StrengthTable strong={sectors.themes_strongest} weak={sectors.themes_weakest}
                       kind="themes" />
      </div>

      {sectors.sector_etfs.length > 0 && (
        <section className="stack" style={{ marginTop: "var(--pad-xl)" }}>
          <h2>Sector ETFs</h2>
          <p className="caption dim">Ranked among themselves, separately from the stocks.</p>
          <div className="scroll-x card" style={{ padding: 0 }}>
            <table className="data">
              <thead>
                <tr><th>Symbol</th><th>RS</th><th>Excess return</th></tr>
              </thead>
              <tbody>
                {sectors.sector_etfs.map((etf) => (
                  <tr key={etf.symbol}>
                    <td className="text mono">{etf.symbol}</td>
                    <td>{etf.rs_rating ?? "—"}</td>
                    <td><PriceChange value={etf.excess_return_pct} digits={1} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <MarketCTA />
    </div>
  );
}
