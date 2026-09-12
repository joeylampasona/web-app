"use client";

/**
 * Hand-authored schematics — not real data, and labelled as such. Tapping any
 * part of the chart highlights the matching concept below; tapping a concept
 * lights it up here. The chart semantics are the same ones used everywhere
 * else on the site: dashed amber pivot, amber-filled current base, dashed grey
 * prior contractions, a gain triangle on the breakout.
 */

const W = 360;
const H = 210;

export function LearnSchematic({
  screen, selected, onSelect,
}: {
  screen: string;
  selected: string | null;
  onSelect: (anchor: string | null) => void;
}) {
  const dim = (anchor: string) => (selected && selected !== anchor ? 0.25 : 1);
  const Part = ({ anchor, children }: { anchor: string; children: React.ReactNode }) => (
    <g
      opacity={dim(anchor)}
      style={{ cursor: "pointer" }}
      onClick={() => onSelect(selected === anchor ? null : anchor)}
      role="button"
      tabIndex={0}
      aria-label={anchor}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          onSelect(selected === anchor ? null : anchor);
        }
      }}
    >
      {children}
    </g>
  );

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
         aria-label={`Schematic of the ${screen} shape`}
         style={{ background: "var(--surface-1)", borderRadius: "var(--radius-card)",
                  border: "0.5px solid var(--border)" }}>
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="var(--gain)" />
        </marker>
      </defs>
      {screen === "vcp" && <Vcp Part={Part} />}
      {screen === "blue_sky" && <BlueSky Part={Part} />}
      {screen === "multi_year" && <MultiYear Part={Part} />}
      {screen === "ipo" && <Ipo Part={Part} />}
      <text x={W - 6} y={H - 4} textAnchor="end" fontSize="7" fill="var(--text-disabled)">
        illustration, not real data
      </text>
    </svg>
  );
}

type PartProps = {
  Part: (props: { anchor: string; children: React.ReactNode }) => React.JSX.Element;
};

const LINE = { fill: "none", stroke: "var(--text-primary)", strokeWidth: 1.4 } as const;
const LABEL = { fontSize: 7, fill: "var(--text-secondary)",
                fontFamily: "var(--font-sans)" } as const;
const EYEBROW = { fontSize: 7, fill: "var(--text-muted)", letterSpacing: "0.08em" } as const;

function Volume({ bars }: { bars: { x: number; h: number; up: boolean }[] }) {
  return (
    <>
      {bars.map((bar) => (
        <rect
          key={bar.x}
          x={bar.x}
          y={196 - bar.h}
          width={4}
          height={bar.h}
          fill={bar.up ? "var(--chart-vol-up)" : "var(--chart-vol-down)"}
        />
      ))}
    </>
  );
}

function Vcp({ Part }: PartProps) {
  const volumes = [
    { x: 14, h: 16, up: true }, { x: 30, h: 20, up: true }, { x: 46, h: 13, up: false },
    { x: 62, h: 22, up: true }, { x: 78, h: 18, up: true }, { x: 94, h: 12, up: false },
    { x: 118, h: 10, up: false }, { x: 134, h: 8, up: false }, { x: 150, h: 9, up: true },
    { x: 166, h: 7, up: false }, { x: 182, h: 6, up: true }, { x: 198, h: 5, up: false },
    { x: 214, h: 5, up: true }, { x: 230, h: 4, up: false },
    { x: 252, h: 26, up: true }, { x: 268, h: 20, up: true }, { x: 300, h: 15, up: true },
  ];
  return (
    <>
      <Part anchor="base">
        <rect x={112} y={70} width={138} height={44} fill="var(--chart-base-fill)"
              stroke="var(--chart-base-line)" strokeWidth={0.75} rx={2} />
        <text x={116} y={64} {...EYEBROW}>FORMING A BASE</text>
      </Part>

      <Part anchor="contractions">
        <rect x={114} y={72} width={40} height={40} fill="none"
              stroke="var(--chart-prior-base)" strokeDasharray="3 3" strokeWidth={0.75} />
        <rect x={156} y={72} width={38} height={28} fill="none"
              stroke="var(--chart-prior-base)" strokeDasharray="3 3" strokeWidth={0.75} />
        <rect x={196} y={72} width={44} height={18} fill="none"
              stroke="var(--chart-prior-base)" strokeDasharray="3 3" strokeWidth={0.75} />
        <text x={118} y={124} {...LABEL}>−22%</text>
        <text x={160} y={124} {...LABEL}>−12%</text>
        <text x={200} y={124} {...LABEL}>−6%</text>
        <text x={150} y={138} {...LABEL}>the swings tighten</text>
      </Part>

      <Part anchor="uptrend">
        <polyline {...LINE} points="10,176 40,152 70,132 100,96 114,74" />
        <text x={14} y={168} {...LABEL}>prior uptrend</text>
      </Part>

      <polyline {...LINE} points="114,74 134,112 154,78 174,100 194,76 214,90 240,74" />

      <Part anchor="pivot">
        <line x1={112} y1={70} x2={352} y2={70} stroke="var(--chart-pivot)"
              strokeWidth={1} strokeDasharray="4 3" />
        <rect x={80} y={64} width={30} height={12} fill="var(--chart-pivot)" rx={2} />
        <text x={95} y={73} textAnchor="middle" fontSize={7} fill="var(--on-brand)"
              fontFamily="var(--font-mono)">87.41</text>
        <text x={250} y={64} {...LABEL}>the ceiling it must clear</text>
      </Part>

      <Part anchor="breakout">
        <polyline {...LINE} points="240,74 258,54" markerEnd="url(#arrow)" />
        <polygon points="252,46 256,53 248,53" fill="var(--gain)" />
        <text x={244} y={40} {...EYEBROW} fill="var(--gain)">BREAKING OUT ↑</text>
      </Part>

      <Part anchor="climbing">
        <polyline {...LINE} points="258,54 290,42 320,32 352,22" />
        <text x={300} y={16} {...EYEBROW} fill="var(--stage-climbing)">CLIMBING</text>
      </Part>

      <Part anchor="volume">
        <Volume bars={volumes} />
        <text x={10} y={206} {...LABEL}>
          <tspan fill="var(--gain)">■</tspan> up days (demand)
          <tspan fill="var(--loss)">  ■</tspan> down days (supply)
        </text>
        <text x={140} y={190} {...LABEL}>volume dries up in the base, demand stays heavier</text>
      </Part>
    </>
  );
}

function BlueSky({ Part }: PartProps) {
  return (
    <>
      <Part anchor="opensky">
        <rect x={10} y={14} width={342} height={52} fill="var(--surface-2)"
              stroke="var(--border)" strokeDasharray="3 3" />
        <text x={16} y={28} {...EYEBROW}>OPEN SKY</text>
        <text x={16} y={40} {...LABEL}>nothing ever traded up here</text>
      </Part>

      <polyline {...LINE} points="10,178 44,160 78,140 112,116 146,92 178,72" />

      <Part anchor="trapped">
        <text x={20} y={150} {...LABEL}>every owner is in profit</text>
      </Part>

      <Part anchor="base">
        <rect x={178} y={66} width={72} height={26} fill="var(--chart-base-fill)"
              stroke="var(--chart-base-line)" strokeWidth={0.75} rx={2} />
        <text x={182} y={104} {...EYEBROW}>BASING AT THE HIGH</text>
      </Part>

      <polyline {...LINE} points="178,72 196,88 214,70 232,82 250,68" />

      <Part anchor="pivot">
        <line x1={178} y1={66} x2={352} y2={66} stroke="var(--chart-pivot)"
              strokeWidth={1} strokeDasharray="4 3" />
        <text x={252} y={60} {...LABEL}>the all-time high — its pivot</text>
      </Part>

      <Part anchor="breakout">
        <polyline {...LINE} points="250,68 272,50" markerEnd="url(#arrow)" />
        <polygon points="266,42 270,49 262,49" fill="var(--gain)" />
        <text x={256} y={36} {...EYEBROW} fill="var(--gain)">BREAKING OUT ↑</text>
      </Part>

      <Part anchor="climbing">
        <polyline {...LINE} points="272,50 310,36 352,24" />
        <text x={306} y={18} {...EYEBROW} fill="var(--stage-climbing)">CLIMBING</text>
      </Part>
    </>
  );
}

function MultiYear({ Part }: PartProps) {
  return (
    <>
      <Part anchor="base">
        <rect x={40} y={58} width={244} height={92} fill="var(--chart-base-fill)"
              stroke="var(--chart-base-line)" strokeWidth={0.75} rx={2} />
        <text x={46} y={52} {...EYEBROW}>52+ WEEKS IN A BASE</text>
      </Part>

      <polyline {...LINE}
                points="10,74 40,60 66,120 96,144 126,132 156,146 186,122 216,108 246,88 276,72" />

      <Part anchor="ma200">
        <path d="M40,96 C90,140 150,148 210,120 C250,102 290,84 352,64"
              fill="none" stroke="var(--chart-ma-200)" strokeWidth={1} />
        <text x={96} y={158} {...LABEL} fill="var(--chart-ma-200)">the 200-day line</text>
      </Part>

      <Part anchor="strength">
        <text x={196} y={136} {...LABEL}>turning back up</text>
      </Part>

      <Part anchor="pivot">
        <line x1={40} y1={58} x2={352} y2={58} stroke="var(--chart-pivot)"
              strokeWidth={1} strokeDasharray="4 3" />
        <text x={230} y={52} {...LABEL}>the lid of a very old base</text>
      </Part>

      <Part anchor="breakout">
        <polyline {...LINE} points="276,72 298,46" markerEnd="url(#arrow)" />
        <polygon points="292,38 296,45 288,45" fill="var(--gain)" />
        <text x={274} y={32} {...EYEBROW} fill="var(--gain)">BREAKING OUT ↑</text>
      </Part>

      <Part anchor="climbing">
        <polyline {...LINE} points="298,46 352,26" />
        <text x={310} y={18} {...EYEBROW} fill="var(--stage-climbing)">CLIMBING</text>
      </Part>
    </>
  );
}

function Ipo({ Part }: PartProps) {
  return (
    <>
      <Part anchor="listing">
        <line x1={30} y1={16} x2={30} y2={190} stroke="var(--text-muted)"
              strokeWidth={1} strokeDasharray="2 3" />
        <text x={34} y={26} {...LABEL}>listing day</text>
      </Part>

      <polyline {...LINE} points="30,150 58,124 86,142 114,104 142,86 170,74" />

      <Part anchor="base">
        <rect x={170} y={68} width={92} height={34} fill="var(--chart-base-fill)"
              stroke="var(--chart-base-line)" strokeWidth={0.75} rx={2} />
        <text x={174} y={114} {...EYEBROW}>ITS FIRST REAL BASE</text>
      </Part>

      <polyline {...LINE} points="170,74 190,98 210,76 230,92 252,72" />

      <Part anchor="ma50">
        <path d="M60,146 C110,128 150,106 200,94 C250,84 300,66 352,50"
              fill="none" stroke="var(--chart-ma-50)" strokeWidth={1} />
        <text x={64} y={158} {...LABEL} fill="var(--chart-ma-50)">
          the 50-day line — holding above it
        </text>
      </Part>

      <Part anchor="pivot">
        <line x1={170} y1={68} x2={352} y2={68} stroke="var(--chart-pivot)"
              strokeWidth={1} strokeDasharray="4 3" />
        <text x={248} y={62} {...LABEL}>the top of its first base</text>
      </Part>

      <Part anchor="breakout">
        <polyline {...LINE} points="252,72 274,50" markerEnd="url(#arrow)" />
        <polygon points="268,42 272,49 264,49" fill="var(--gain)" />
        <text x={250} y={36} {...EYEBROW} fill="var(--gain)">BREAKING OUT ↑</text>
      </Part>

      <Part anchor="climbing">
        <polyline {...LINE} points="274,50 312,38 352,26" />
        <text x={306} y={18} {...EYEBROW} fill="var(--stage-climbing)">CLIMBING</text>
      </Part>
    </>
  );
}
