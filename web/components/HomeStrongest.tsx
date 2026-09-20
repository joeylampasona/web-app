import Link from "next/link";
import type { GroupRow } from "@/lib/types";
import { StageBadge } from "./Badges";
import { TickerLink } from "./StockDrawer";
import { rsText } from "@/lib/format";

/**
 * The strongest industry, theme and stock, in one row.
 *
 * The stock carries its stage, and that is not decoration. The highest-RS name
 * in the market is very often the one that has already run and is the worst
 * thing to buy that morning; printing "RS 99" beside a ticker with nothing else
 * reads as a recommendation this site is not making. "Played out" beside it is
 * the difference between information and a tip.
 *
 * Each card links to the page that shows the working, because a single name
 * pulled out of a ranking is an invitation to check it, not a conclusion.
 */

export interface StrongestStock {
  symbol: string;
  name: string;
  rs_rating: number | string;
  stage: string | null;
}

/** How much of a group is actually leading, as a bar rather than a sentence.
 *
 * "16 of 22 are leaders" and "3 of 22 are leaders" read almost identically at a
 * glance, and they are the difference between a group that is moving and one
 * with a single name dragging its average up. The bar makes that the first
 * thing you see; the sentence stays underneath, because the bar alone does not
 * say what is being counted.
 *
 * The fill is the brand accent rather than the gain colour: this is a measure
 * of breadth, not of a price going up, and --gain elsewhere on the site always
 * means the latter.
 */
function LeaderShare({ leaders, members }: { leaders: number; members: number }) {
  const share = members > 0 ? Math.min(Math.max(leaders / members, 0), 1) : 0;
  return (
    <div className="stack" style={{ gap: 4 }}>
      <div
        role="img"
        aria-label={`${leaders} of ${members} are leaders`}
        style={{
          height: 5, borderRadius: "var(--radius-pill)",
          // --border-stronger, not --surface-3: surface-3 is #FFFFFF on the
          // light theme, so the unfilled track would have disappeared into the
          // card it sits on. The border tokens are the theme-aware pair.
          background: "var(--border-stronger)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${share * 100}%`, height: "100%",
            background: "var(--brand)", borderRadius: "var(--radius-pill)",
          }}
        />
      </div>
      <div className="caption dim" aria-hidden>
        {leaders} of {members} are leaders
      </div>
    </div>
  );
}

function Card({
  eyebrow, title, href, rs, children,
}: {
  eyebrow: string; title: string; href: string;
  rs: number | string | null | undefined;
  children?: React.ReactNode;
}) {
  return (
    <Link href={href} className="card stack" style={{ gap: "var(--gap-xs)", textDecoration: "none" }}>
      <div className="footnote muted">{eyebrow}</div>
      <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
        <span style={{ fontWeight: 500, minWidth: 0 }}>{title}</span>
        <span className="num footnote" style={{ flexShrink: 0 }}>{rsText(rs)}</span>
      </div>
      {children}
    </Link>
  );
}

export function HomeStrongest({
  industry, theme, stock,
}: {
  industry: GroupRow | null;
  theme: GroupRow | null;
  stock: StrongestStock | null;
}) {
  if (!industry && !theme && !stock) return null;

  return (
    <section className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
        <div className="eyebrow">Strongest right now</div>
        <Link href="/market/sectors" className="footnote"
              style={{ textDecoration: "underline", whiteSpace: "nowrap" }}>
          All of them
        </Link>
      </div>
      <div className="grid-auto">
        {industry && (
          <Card eyebrow="Industry" title={industry.name}
                href={`/industries/${industry.slug}`} rs={industry.rs_rating}>
            <LeaderShare leaders={industry.leaders} members={industry.members} />
          </Card>
        )}
        {theme && (
          <Card eyebrow="Theme" title={theme.name}
                href={`/themes/${theme.slug}`} rs={theme.rs_rating}>
            <LeaderShare leaders={theme.leaders} members={theme.members} />
          </Card>
        )}
        {stock && (
          <div className="card stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="footnote muted">Stock</div>
            <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
              <TickerLink symbol={stock.symbol} className="mono" style={{ fontWeight: 500 }}>
                {stock.symbol}
              </TickerLink>
              <span className="num footnote" style={{ flexShrink: 0 }}>
                {rsText(stock.rs_rating)}
              </span>
            </div>
            <div className="row" style={{ gap: "var(--gap-sm)", alignItems: "baseline", minWidth: 0 }}>
              <span className="caption dim" style={{
                minWidth: 0, overflow: "hidden",
                textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                {stock.name}
              </span>
              {stock.stage && <StageBadge stage={stock.stage} />}
            </div>
            {!stock.stage && (
              <div className="caption dim">Not in any screen — strength without a base.</div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
