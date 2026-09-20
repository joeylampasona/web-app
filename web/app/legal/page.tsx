import type { Metadata } from "next";
import { getMeta } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const metadata: Metadata = {
  title: `Disclaimer — ${SITE_NAME}`,
  description: "What this site is, what it is not, and what its numbers mean.",
};

export default function LegalPage() {
  const meta = getMeta();
  const live = meta?.data_source === "live";

  return (
    <div className="page stack" style={{ gap: "var(--pad-lg)" }}>
      <div>
        <div className="eyebrow">Disclaimer</div>
        <h1 style={{ marginBottom: "var(--gap-sm)" }}>What this is, and what it is not</h1>
        <p className="muted footnote" style={{ margin: 0 }}>
          Last updated with the site itself. Read this before acting on anything here.
        </p>
      </div>

      <Section title="Not investment advice">
        <p>
          {SITE_NAME} is a screening and market-analytics tool. It shows you
          where prices have been and flags shapes in them. It does not tell you what
          to buy, what to sell, or when.
        </p>
        <p>
          We are not a registered investment adviser, a broker-dealer, or a financial
          planner, and nothing here is personalised advice. Nothing on this site takes
          account of your circumstances, your goals, your tax position, or how much you
          can afford to lose — because it knows none of those things.
        </p>
        <p>
          There is no order-placing code in this project and there never will be.
        </p>
      </Section>

      <Section title="A pattern is not a prediction">
        <p>
          The screens find structures — a base, a pivot, a stretch of tightening range.
          A stock appearing on a screen means it currently matches a shape. It does not
          mean the shape will resolve upward, or at all.
        </p>
        <p>
          This is not hedging for the sake of it. An out-of-sample study on a US universe
          found that the <em>structural</em> components of these patterns carried no
          measurable edge on their own. The one component with statistical support was
          relative strength. That result is why relative strength is the primary ranking
          everywhere on this site and why base detection is presented as a timing and
          presentation layer rather than as a reason to expect a return.
        </p>
      </Section>

      <Section title="What we show about past breakouts">
        <p>
          The &ldquo;Did it work?&rdquo; page replays breakouts this site showed and
          reports what the price did afterwards. It is a record of outcomes, not a
          strategy return: no position sizing, no costs, no entry or exit you could
          actually have got. It does not tell you what the next one will do.
        </p>
        <p>
          One limitation is large enough to state rather than footnote.{" "}
          <strong>Survivorship bias.</strong> Our data source&rsquo;s free tier carries
          no delisted companies, so every historical figure here only ever saw names
          that survived to today. The companies that failed are simply absent, every
          figure is flattered by this, and we cannot tell you by how much.
        </p>
      </Section>

      <Section title="Where the numbers come from">
        <p>
          Prices come from a market-data provider and are end-of-day, not live. Nothing
          on this site is a real-time quote. Company details come from SEC filings.
          Earnings dates and options data come from a public, unofficial source and are
          best-effort — when they are unavailable the site shows less rather than
          guessing.
        </p>
        <p>
          {live
            ? "The data on this build is real market data, refreshed after each close."
            : "The data on this build is a deterministic fixture, not real market data. "
              + "Tickers and company names on it are invented."}{" "}
          Data can be wrong, late, or missing. We do not warrant that any figure here is
          accurate or complete, and you should verify anything that matters against your
          broker or the primary source.
        </p>
      </Section>

      <Section title="Accounts and your data">
        <p>
          You can use almost all of this site without an account. An account exists so
          that a watchlist and your saved screens follow you between devices.
        </p>
        <p>
          If you make one, it holds your email address, your watchlist and your saved
          screens. Sign-in is a one-time emailed code, so there is no password for us to
          store or lose. We do not sell anything to anyone, and there is no advertising
          on this site.
        </p>
      </Section>

      <Section title="No warranty, no liability">
        <p>
          This site is provided as it is, without warranty of any kind. It may be wrong,
          it may be down, and it may change without notice. To the fullest extent the law
          allows, we are not liable for any loss arising from your use of it or from
          anything you decide after reading it.
        </p>
        <p>
          Trading and investing carry risk, including the risk of losing more than you put
          in. Past performance does not indicate future results. If you need advice, get
          it from someone licensed to give it to you.
        </p>
      </Section>

      <Section title="Getting in touch">
        <p>
          Anything on this page, a correction to a number, or a request to delete
          your account and everything on it:{" "}
          <a href="mailto:hello@thetape.cc" className="mono"
             style={{ color: "var(--link)" }}>hello@thetape.cc</a>.
        </p>
        <p>
          Deletion is done by hand and takes a day or two. It removes the account,
          the watchlist and the saved screens; nothing is kept back.
        </p>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card stack" style={{ gap: "var(--gap-sm)", alignItems: "stretch" }}>
      <h2 style={{ fontSize: "var(--size-h3)", fontWeight: 500, margin: 0 }}>{title}</h2>
      <div className="stack footnote muted" style={{ gap: "var(--gap-sm)" }}>{children}</div>
    </section>
  );
}
