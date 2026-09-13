import { BreakoutBrowser } from "@/components/BreakoutBrowser";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { EAGER_CHARTS, barsFor, getBreakoutDates, getBreakouts, getMeta, hasData } from "@/lib/data";

export default function BreakoutsPage() {
  if (!hasData()) return <NoData />;
  const dates = getBreakoutDates();
  const latest = dates[0];
  const file = latest ? getBreakouts(latest) : null;
  const setups = file?.setups ?? [];

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · the lay of the land</div>
      <h1>All breakouts today</h1>
      <p className="muted footnote">
        Every name on one of the four screens that closed above its pivot on the session
        you pick. The metric rows swap to the breakout set here.
      </p>
      {latest ? (
        <BreakoutBrowser
          dates={dates}
          initialDate={latest}
          setups={setups}
          bars={barsFor(setups.map((s) => s.symbol).slice(0, EAGER_CHARTS))}
        />
      ) : (
        <div className="card muted footnote">No sessions published yet.</div>
      )}
      <MarketCTA />
    </div>
  );
}
