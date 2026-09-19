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
            <div className="caption dim">
              {industry.leaders} of {industry.members} are leaders
            </div>
          </Card>
        )}
        {theme && (
          <Card eyebrow="Theme" title={theme.name}
                href={`/themes/${theme.slug}`} rs={theme.rs_rating}>
            <div className="caption dim">
              {theme.leaders} of {theme.members} are leaders
            </div>
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
