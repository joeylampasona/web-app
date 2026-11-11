import Link from "next/link";
import { TOTAL_TESTS, type MarketRead } from "@/lib/marketRead";
import type { Radar } from "@/lib/types";

/**
 * The lead: the market read as a headline, with its arithmetic beside it.
 *
 * Set like the front of a market page rather than boxed in a card. The claim
 * is the largest type on the site, the phrase that carries it is marked with
 * the highlighter, and the four checks that produced it sit directly under
 * it as a meter: one cell per check, lit when it is in gear, each with its
 * own reading and the last twenty sessions of the number it reads. The
 * evidence stays attached to the claim so a reader can disagree with it.
 *
 * Beside it, where strength sits: the radar's label for the week and its four
 * key ratios as bars from a centre line, right for ahead, left for behind.
 *
 * Colour never carries the verdict alone. Each cell prints its reading and
 * says in words whether it is in gear.
 */
const STATE: Record<string, string> = { "1": "In gear", "0": "Neither", "-1": "Against" };
/** One ratio's bar runs out to this many percent either side of the centre. */
const RATIO_SCALE = 8;

export function Headline({ text }: { text: string }) {
  // "The tape is in gear" marks "in gear"; a headline with no such lead-in is
  // marked whole.
  const lead = "The tape is ";
  if (text.startsWith(lead)) {
    return <>{lead}<span className="hl">{text.slice(lead.length)}.</span></>;
  }
  // "Mixed, under a falling benchmark" marks "Mixed".
  const comma = text.indexOf(",");
  if (comma > 0) return <><span className="hl">{text.slice(0, comma)}</span>{text.slice(comma)}.</>;
  return <span className="hl">{text}.</span>;
}

function signed(v: number): string {
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}%`;
}

export function HomeRead({
  read, session, series, radar, actions,
}: {
  read: MarketRead;
  session: string;
  /** The last twenty sessions of each check's own number, by check key. */
  series: Record<string, number[]>;
  radar: Radar | null;
  /** What a reader can do with the read: share it, page back through it. */
  actions?: React.ReactNode;
}) {
  const inGear = read.tests.filter((t) => t.score === 1).length;
  return (
    <section className="read-split">
      <div className="lead stack" style={{ gap: "var(--gap-lg)" }}>
        <div className="kicker">
          The read · {session}
          {read.tests.length > 0 && <> · {inGear} of {read.tests.length} checks in gear</>}
        </div>
        <h1 className="read-headline"><Headline text={read.headline} /></h1>
        <p style={{ margin: 0, maxWidth: "58ch", fontSize: "var(--size-lead)",
                    color: "var(--text-secondary)" }}>
          {read.blurb}
        </p>

        {read.tests.length > 0 && (
          <div className="meter">
            {read.tests.map((test) => {
              const points = series[test.key] ?? [];
              const max = Math.max(...points, 0);
              return (
                <div key={test.key} className="meter-cell"
                     data-lit={test.score === 1 ? "true" : test.score === -1 ? "against" : "false"}>
                  <div className="label-caps" style={{ color: "var(--text-muted)" }}>{test.label}</div>
                  <div className="meter-value">{test.value}</div>
                  <div className="caption" style={{ color: "var(--text-secondary)" }}>
                    {STATE[String(test.score)]}
                  </div>
                  {points.length > 1 && max > 0 && (
                    <div className="minibars" role="img"
                         aria-label={`${test.label}, last ${points.length} sessions`}>
                      {points.map((v, i) => (
                        <span key={i} style={{ height: `${Math.max(6, (v / max) * 100)}%` }} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <p className="caption" style={{ margin: 0, color: "var(--text-muted)" }}>
          {read.measured === TOTAL_TESTS
            ? "Four checks on the published numbers, nothing else. Bars are the last twenty sessions."
            : `${read.measured} of ${TOTAL_TESTS} checks had data in the last run.`}{" "}
          <Link href="/market/breadth" style={{ textDecoration: "underline" }}>
            What each one counts
          </Link>
        </p>
        {actions && (
          <div className="row wrap" style={{ gap: "var(--gap-sm)", alignItems: "center" }}>{actions}</div>
        )}
      </div>

      {radar && (
        <aside className="side stack" style={{ gap: "var(--gap-md)" }}>
          <div className="kicker">Where strength sits · six months</div>
          <h2 style={{ fontSize: "clamp(30px, 3.4vw, 42px)" }}>
            <Link href="/market/radar">{radar.read.label}</Link>
          </h2>
          <p className="footnote" style={{ margin: 0, color: "var(--text-secondary)" }}>
            {radar.read.sub} {radar.read.full_share}% of groups fully aligned.
          </p>
          <div className="stack" style={{ gap: "var(--gap-md)", marginTop: "var(--gap-xs)" }}>
            {radar.pairs.map((p) => {
              const v = p.now.rs126;
              if (v == null) return null;
              const width = Math.min(50, (Math.abs(v) / RATIO_SCALE) * 50);
              const tone = v >= 0 ? "var(--gain)" : "var(--loss)";
              return (
                <div key={`${p.a}/${p.b}`} className="stack" style={{ gap: 5 }}>
                  <div className="between footnote" style={{ alignItems: "baseline" }}>
                    <span>
                      <span style={{ fontWeight: 500 }}>{p.label}</span>{" "}
                      <span className="mono caption dim">{p.a} / {p.b}</span>
                    </span>
                    <span className="num" style={{ fontWeight: 600, color: tone }}>{signed(v)}</span>
                  </div>
                  <div className="diverge" aria-hidden>
                    <span className="bar" style={{
                      background: tone, width: `${width}%`,
                      left: v >= 0 ? "50%" : `${50 - width}%`,
                    }} />
                    <span className="mid" />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="caption dim" style={{ margin: 0 }}>
            Bars run from the centre line: right is ahead, left is behind, out
            to ±{RATIO_SCALE}%.
          </p>
        </aside>
      )}
    </section>
  );
}
