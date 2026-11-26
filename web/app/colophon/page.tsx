import type { Metadata } from "next";
import Link from "next/link";
import { ColophonQuotes } from "@/components/ColophonQuotes";
import { DataBanner, NoData } from "@/components/DataBanner";
import { shortDay } from "@/components/CarriedOver";
import { getMeta, hasData } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";
import type { SourceStatus } from "@/lib/types";

export const metadata: Metadata = {
  title: `How this edition was made — ${SITE_NAME}`,
  description: "Which sources tonight's pages were built from, what each one gave, "
               + "and which figures are carried over from an earlier night.",
};

/**
 * The colophon: how tonight's edition was made.
 *
 * A printed page says at the back who set it and on what. This is that page.
 * Every figure on the site comes from a handful of sources fetched once a
 * night, and on any given night one of them may answer in part, answer with
 * an older day, or not answer. The pipeline keeps what it had rather than
 * leave a hole, which is right and is also invisible. In one week an options
 * source closed its door and a feeder stopped updating, and nothing on the
 * site said either had happened.
 *
 * So the pipeline now counts what each source gave it and writes the count
 * into the edition, and this page prints it: one row a source, a word for how
 * it did, and the pipeline's own sentence about it. The words are the status.
 * The swatch beside each only repeats it.
 */
const STATUS: Record<SourceStatus, { word: string; tone: string; means: string }> = {
  ok: { word: "Fresh", tone: "var(--gain)", means: "answered in full for this session" },
  partial: { word: "Partial", tone: "var(--warn)", means: "answered with less than it should have" },
  behind: { word: "Behind", tone: "var(--warn)", means: "answered with an older day" },
  down: { word: "Down", tone: "var(--loss)", means: "did not answer; the pages show what was kept" },
};

function generated(iso: string | undefined): string | null {
  if (!iso) return null;
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return null;
  return `${when.toLocaleString("en-US", {
    timeZone: "America/New_York", weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  })} ET`;
}

function longDay(iso: string | undefined): string | null {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return null;
  return new Date(`${iso.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "UTC",
  });
}

export default function ColophonPage() {
  if (!hasData()) return <NoData />;
  const meta = getMeta();
  if (!meta) return <NoData />;

  const sources = (meta.sources ?? []).filter((s) => s && s.label);
  const short = sources.filter((s) => s.status !== "ok");
  const facts: [string, string][] = [
    ["Session", longDay(meta.as_of) ?? meta.as_of],
    ["Set", generated(meta.generated_at) ?? "Not recorded"],
    ["Universe", `${meta.universe_count.toLocaleString("en-US")} liquid US names`],
    ["Screens", `${meta.screens.length} patterns, ${meta.screens
      .reduce((sum, s) => sum + s.total, 0).toLocaleString("en-US")} setups`],
  ];

  return (
    <div className="page stack" style={{ gap: "var(--pad-xl)" }}>
      <DataBanner meta={meta} />

      <header className="colophon-head stack" style={{ gap: "var(--gap-md)" }}>
        <div className="kicker">Colophon · {shortDay(meta.as_of)} edition</div>
        <h1 className="colophon-title">
          How this edition was <span className="hl">made</span>.
        </h1>
        <p style={{ margin: 0, maxWidth: "62ch", fontSize: "var(--size-lead)",
                    color: "var(--text-secondary)" }}>
          Every figure here is fetched once a night from the sources below, then
          ranked and screened. When a source answers in part, or not at all, the
          pages keep what they had and say so. This is the count.
        </p>
      </header>

      <dl className="colophon-facts">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt className="label-caps">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <section className="stack" style={{ gap: "var(--gap-md)" }}>
        <div className="ruled-head">
          <h2>The sources</h2>
          <span className="kicker">
            {sources.length === 0
              ? "No report in this edition"
              : short.length === 0
                ? `All ${sources.length} answered in full`
                : `${short.length} of ${sources.length} short or behind`}
          </span>
        </div>

        {sources.length === 0 && (
          <p className="footnote muted" style={{ margin: 0, maxWidth: "70ch" }}>
            This edition was set before the pipeline began counting what each
            source gave it. The report starts with the next nightly; until then
            only the intraday prices below can speak for themselves.
          </p>
        )}

        <div className="colophon-table" role="table" aria-label="Sources for this edition">
          <div className="colophon-row colophon-row--head" role="row">
            <span role="columnheader" className="label-caps">Source</span>
            <span role="columnheader" className="label-caps">Status</span>
            <span role="columnheader" className="label-caps">What it gave</span>
            <span role="columnheader" className="label-caps">Covers</span>
          </div>
          {sources.map((source) => {
            const status = STATUS[source.status] ?? STATUS.ok;
            return (
              <div key={source.key} className="colophon-row" role="row"
                   data-status={source.status}>
                <span role="cell" className="stack" style={{ gap: 2 }}>
                  <span className="colophon-name">{source.label}</span>
                  <span className="caption dim">{source.from}</span>
                </span>
                <span role="cell" className="colophon-status" title={status.means}>
                  <span className="colophon-swatch" aria-hidden style={{ background: status.tone }} />
                  {status.word}
                </span>
                <span role="cell" className="footnote">{source.detail}</span>
                <span role="cell" className="num footnote" style={{ whiteSpace: "nowrap" }}>
                  {shortDay(source.as_of) ?? "—"}
                </span>
              </div>
            );
          })}
          <ColophonQuotes asOf={meta.as_of} />
        </div>

        <p className="caption dim" style={{ margin: 0, maxWidth: "78ch" }}>
          {(Object.keys(STATUS) as SourceStatus[]).map((key, index) => (
            <span key={key}>
              {index > 0 && " · "}
              <strong style={{ fontWeight: 600, color: "var(--text-secondary)" }}>
                {STATUS[key].word}
              </strong>{" "}
              {STATUS[key].means}
            </span>
          ))}
          . A figure kept from an earlier night is marked <span className="carried">Carried over</span>{" "}
          on the page that shows it.
        </p>
      </section>

      <section className="home-section stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="kicker">Also</div>
        <p className="footnote muted" style={{ margin: 0, maxWidth: "70ch" }}>
          Each night&rsquo;s read is kept as it was published in the{" "}
          <Link href="/market/editions" style={{ textDecoration: "underline" }}>back issues</Link>.
          What a screen result is and is not is set out in the{" "}
          <Link href="/legal" style={{ textDecoration: "underline" }}>full disclaimer</Link>.
          {meta.survivorship_safe === false && (
            <> The universe is today&rsquo;s listed names, so history here leaves
            out companies that have since delisted.</>
          )}
        </p>
        {meta.sp500 && (
          <p className="footnote muted" style={{ margin: 0, maxWidth: "70ch" }}>
            The S&amp;P 500 tag on a company&rsquo;s page and the filter on a screen
            come from the public constituents list kept at{" "}
            <a href="https://github.com/datasets/s-and-p-500-companies"
               rel="noopener noreferrer" style={{ textDecoration: "underline" }}>
              github.com/datasets</a>, fetched once a week. It is a convenience
            copy and not S&amp;P&rsquo;s own publication.
            {meta.sp500.fetched_on && (
              <> Last fetched {shortDay(meta.sp500.fetched_on)}: {meta.sp500.listed
                .toLocaleString("en-US")} lines, {meta.sp500.members_in_universe
                .toLocaleString("en-US")} of them in this universe.</>
            )}
          </p>
        )}
        {/* The chart library's licence asks for its notice and a link on a
            page readers can reach. This is that page. */}
        <p className="footnote muted" style={{ margin: 0, maxWidth: "70ch" }}>
          The price charts are drawn with TradingView Lightweight Charts&trade;,
          Copyright &copy; 2025 TradingView, Inc.{" "}
          <a href="https://www.tradingview.com/" rel="noopener noreferrer"
             style={{ textDecoration: "underline" }}>https://www.tradingview.com/</a>
        </p>
      </section>
    </div>
  );
}
