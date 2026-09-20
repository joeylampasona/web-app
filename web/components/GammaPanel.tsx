import type { GammaProfile } from "@/lib/types";

/**
 * Where open interest concentrates option gamma.
 *
 * The ordering of this panel is the argument it is making. Concentration comes
 * first and gets the chart, because it is arithmetic over two published facts:
 * how many contracts are open at a strike, and what they are worth in gamma.
 * Nothing about it depends on knowing who is long and who is short.
 *
 * The signed reading — the one usually called GEX, calls positive and puts
 * negative — comes second, in smaller type, with the assumption it rests on
 * written next to it rather than in a tooltip. Open interest does not say who
 * holds which side; "dealers are long calls and short puts" is a convention,
 * and a widely disputed one. Presenting the two readings at the same visual
 * weight would imply they are equally well founded, and they are not.
 */
export function GammaPanel({ gamma }: { gamma: GammaProfile | null }) {
  if (!gamma || gamma.levels.length === 0) {
    return (
      <p className="muted footnote">
        No option open interest for this company. Most listed names have no
        options at all, and we only read chains for names carrying a dated
        event, so this is a normal reading rather than a fault.
      </p>
    );
  }

  const { levels, spot, flip } = gamma;
  const peak = Math.max(...levels.map((l) => l.concentration)) || 1;
  const strikes = levels.map((l) => l.strike);
  const nearest = strikes.reduce((best, s) =>
    Math.abs(s - spot) < Math.abs(best - spot) ? s : best, strikes[0]);

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <p className="muted footnote" style={{ margin: 0 }}>
        How much option gamma sits at each strike, counting every open contract
        across the next {gamma.expiries} expir{gamma.expiries === 1 ? "y" : "ies"}.
        Bigger bars mean more optionality anchored there.
      </p>

      <div className="stack" style={{ gap: 2 }}>
        {levels.map((level) => {
          const width = Math.max((level.concentration / peak) * 100, 1.5);
          const atSpot = level.strike === nearest;
          return (
            <div
              key={level.strike}
              className="row"
              style={{ gap: "var(--gap-sm)", alignItems: "center" }}
            >
              <span
                className="num caption"
                style={{
                  minWidth: 62, textAlign: "right",
                  color: atSpot ? "var(--brand-ink)" : "var(--text)",
                  fontWeight: atSpot ? 600 : 400,
                }}
              >
                {level.strike.toFixed(2)}
              </span>
              <span
                aria-hidden
                style={{
                  height: 12, width: `${width}%`, borderRadius: 2,
                  background: atSpot ? "var(--brand)" : "var(--screen-highs)",
                  opacity: atSpot ? 1 : 0.75,
                }}
              />
              <span className="caption dim num" style={{ whiteSpace: "nowrap" }}>
                {compact(level.concentration)}
              </span>
            </div>
          );
        })}
      </div>

      <p className="caption dim" style={{ margin: 0 }}>
        Spot {spot.toFixed(2)}
        {" · "}
        {gamma.open_interest.toLocaleString()} contracts open across{" "}
        {levels.length} strikes within 30% of it
        {gamma.stale && " · open interest is from the previous session"}
      </p>

      <div
        className="stack"
        style={{
          gap: "var(--gap-xs)", paddingTop: "var(--pad-md)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <div className="row" style={{ gap: "var(--gap-md)", flexWrap: "wrap" }}>
          <Figure label="Net, calls minus puts" value={compact(gamma.total_net, true)} />
          <Figure label="Sign crosses zero at"
                  value={flip === null ? "no crossing" : flip.toFixed(2)} />
        </div>
        <p className="caption dim" style={{ margin: 0 }}>
          These two treat calls as positive and puts as negative. That is the
          usual convention and it assumes market makers are long calls and short
          puts — open interest says how many contracts exist, not who holds
          which side of them. The bars above do not rely on that assumption;
          these two numbers do. Neither predicts where the price goes.
        </p>
      </div>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <span className="stack" style={{ gap: 0 }}>
      <span className="num" style={{ fontSize: "var(--size-h3)" }}>{value}</span>
      <span className="caption dim">{label}</span>
    </span>
  );
}

/** Dollar gamma runs to tens of millions; the exact digits are noise here. */
function compact(value: number, signed = false): string {
  const sign = signed && value > 0 ? "+" : value < 0 ? "−" : "";
  const n = Math.abs(value);
  if (n >= 1e9) return `${sign}$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${sign}$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${sign}$${(n / 1e3).toFixed(0)}K`;
  return `${sign}$${n.toFixed(0)}`;
}
