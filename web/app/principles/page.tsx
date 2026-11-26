import Link from "next/link";

export const metadata = {
  title: "How The Tape is made",
  description: "The rules the site holds itself to, and where each one shows on the page.",
};

/**
 * The house rules, each with the place on the site where a reader can check
 * it. Written from DECISIONS.md: nothing here is a promise the pipeline does
 * not already keep.
 */
const RULES: { title: string; says: string; where: { href: string; label: string }[] }[] = [
  {
    title: "End of day, and said so",
    says: "The screens are built from settled closes. The prices between sessions are delayed quotes, labelled as delayed, and never mixed into what a screen measures.",
    where: [{ href: "/colophon", label: "How this edition was made" }],
  },
  {
    title: "A shape, not a call",
    says: "A stock on a screen matches a pattern. That is a description of its chart. Nothing here tells anyone to buy, sell or size a position.",
    where: [{ href: "/screens", label: "What each screen looks for" }],
  },
  {
    title: "Every screen is graded",
    says: "Each breakout is followed for twenty sessions and counted, up or down, against the S&P 500. A screen that lags on enough breakouts is marked on watch, with the numbers that put it there. It is never quietly dropped.",
    where: [{ href: "/market/record", label: "The record" }, { href: "/market/followthrough", label: "Did it work?" }],
  },
  {
    title: "The failures are kept",
    says: "Every question put to real data is written down with what was measured and how it came out, including the ideas the data refused.",
    where: [{ href: "/market/research", label: "What we tested" }],
  },
  {
    title: "Every source says how its night went",
    says: "When a source is down, late or answering in part, the edition says which one and what it affects. A figure carried over from an earlier night is marked with the night it is from.",
    where: [{ href: "/colophon", label: "Tonight's source report" }],
  },
  {
    title: "Say what we cannot know",
    says: "A number we cannot stand behind is left blank rather than guessed. Market caps from one share class are labelled as a floor. Gamma is reported as concentration, and the signed figure is marked as resting on an assumption about who holds which side.",
    where: [{ href: "/market/gamma", label: "Gamma concentration" }],
  },
  {
    title: "What a model read is labelled as such",
    says: "The first read of a quarter is taken from the company's press release by a model, the evening it reports, and the card says so. The read the site stands behind waits for the filed 10-Q.",
    where: [{ href: "/market/earnings", label: "Earnings" }],
  },
  {
    title: "Primary sources first",
    says: "Company figures come from SEC filings, option open interest from the clearing house, trades by members of the House from the Clerk's own reports. Where a free source is a copy of someone else's, the page says so.",
    where: [{ href: "/colophon", label: "Sources" }],
  },
];

export default function PrinciplesPage() {
  return (
    <div className="page">
      <div className="eyebrow">About · the house rules</div>
      <h1 style={{ marginBottom: "var(--gap-sm)" }}>How The Tape is made</h1>
      <p style={{ margin: "0 0 var(--pad-lg)", maxWidth: "64ch", color: "var(--text-secondary)" }}>
        Most market sites hand you every number they have. This one tries to
        show what a chart is doing, say how sure it is, and keep score of
        itself where you can see it. These are the rules it is built to, and
        where on the site you can check each one.
      </p>
      <ol className="stack" style={{ listStyle: "none", padding: 0, margin: 0, gap: "var(--pad-lg)", maxWidth: "72ch" }}>
        {RULES.map((rule, index) => (
          <li key={rule.title} style={{ borderTop: "1px solid var(--rule)", paddingTop: "var(--pad)" }}>
            <div className="caption dim" style={{ fontVariantNumeric: "tabular-nums" }}>
              {String(index + 1).padStart(2, "0")}
            </div>
            <h2 style={{ margin: "var(--gap-xs) 0" }}>{rule.title}</h2>
            <p style={{ margin: "0 0 var(--gap-sm)" }}>{rule.says}</p>
            <p className="caption" style={{ margin: 0 }}>
              {rule.where.map((w, i) => (
                <span key={w.href + w.label}>
                  {i > 0 ? " · " : "See: "}
                  <Link href={w.href} style={{ color: "var(--link)", textDecoration: "underline" }}>{w.label}</Link>
                </span>
              ))}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}
