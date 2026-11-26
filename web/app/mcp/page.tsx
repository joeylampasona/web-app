import type { Metadata } from "next";
import Link from "next/link";
import { SITE_NAME } from "@/lib/copy";
import { PROTOCOL_VERSIONS } from "@/lib/mcp/protocol";
import { SERVER } from "@/lib/mcp/tools";
import { SITE_ORIGIN } from "@/lib/share";

export const metadata: Metadata = {
  title: `Ask with your own AI — ${SITE_NAME}`,
  description: `Connect Claude, Cursor or any MCP client to ${SITE_NAME} with one line, `
               + "and ask it about the screens, a company or the day's edition.",
};

/**
 * How to plug a reader's own AI into the site.
 *
 * The list of tools on this page is read from the server's own definition,
 * not written out again here, so the page cannot describe a tool the
 * endpoint does not have.
 */
const ENDPOINT = `${SITE_ORIGIN}/api/mcp`;

const CLAUDE = `claude mcp add --transport http the-tape ${ENDPOINT}`;

const JSON_CONFIG = `{
  "mcpServers": {
    "the-tape": {
      "type": "http",
      "url": "${ENDPOINT}"
    }
  }
}`;

const QUESTIONS = [
  "What did The Tape's edition say about the market last night, and which sources were stale?",
  "Which screens have the most names forming, and what does each one look for?",
  "Look up NVDA: what setup is it in, where is the pivot, and when does it report?",
  "Who reported today, how did the price take it, and did the move stay inside what options priced?",
  "Is breadth better or worse than a week ago?",
];

function Code({ children, label }: { children: string; label: string }) {
  return (
    <pre aria-label={label} className="num"
         style={{ margin: 0, padding: "var(--pad-md)", border: "1px solid var(--rule)",
                  background: "var(--surface-1)", overflowX: "auto", fontSize: "var(--size-footnote)",
                  lineHeight: 1.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxWidth: "100%" }}>
      <code>{children}</code>
    </pre>
  );
}

export default function McpPage() {
  return (
    <div className="page stack" style={{ gap: "var(--pad-xl)" }}>
      <header className="colophon-head stack" style={{ gap: "var(--gap-md)" }}>
        <div className="kicker">For your own AI</div>
        <h1 className="colophon-title">
          Ask it <span className="hl">yourself</span>.
        </h1>
        <p style={{ margin: 0, maxWidth: "62ch", fontSize: "var(--size-lead)",
                    color: "var(--text-secondary)" }}>
          {SITE_NAME} speaks the Model Context Protocol, so Claude, Cursor or any
          other client that does can read these pages for you. One line connects
          it. After that you ask in your own words and it looks things up here.
        </p>
      </header>

      <section className="stack" style={{ gap: "var(--gap-md)" }}>
        <div className="ruled-head">
          <h2>Connect</h2>
          <span className="kicker">One line</span>
        </div>
        <p className="footnote" style={{ margin: 0, maxWidth: "70ch" }}>
          In Claude Code, run this once in a terminal:
        </p>
        <Code label="The command for Claude Code">{CLAUDE}</Code>
        <p className="footnote" style={{ margin: 0, maxWidth: "70ch" }}>
          In a client that takes a JSON file of servers, add this entry. The
          address is all there is: no key, no sign-in.
        </p>
        <Code label="The entry for a JSON configuration">{JSON_CONFIG}</Code>
        <p className="footnote muted" style={{ margin: 0, maxWidth: "70ch" }}>
          The endpoint is <span className="num">{ENDPOINT}</span>, over
          HTTP, protocol revisions {PROTOCOL_VERSIONS.join(", ")}. A client that
          asks for a newer one is offered the newest of these.
        </p>
      </section>

      <section className="stack" style={{ gap: "var(--gap-md)" }}>
        <div className="ruled-head">
          <h2>What it can look up</h2>
          <span className="kicker">{SERVER.tools.length} tools, all read-only</span>
        </div>
        <div className="colophon-table" role="table" aria-label="The tools">
          {SERVER.tools.map((tool) => (
            <div key={tool.name} role="row"
                 style={{ display: "grid", gap: "var(--gap-xs)", padding: "var(--pad-sm) 0",
                          borderBottom: "1px solid var(--rule)" }}>
              <span role="cell" className="stack" style={{ gap: 2 }}>
                <span className="colophon-name">{tool.title}</span>
                <span className="caption dim num">{tool.name}</span>
              </span>
              <span role="cell" className="footnote" style={{ maxWidth: "78ch" }}>
                {tool.description}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="stack" style={{ gap: "var(--gap-md)" }}>
        <div className="ruled-head">
          <h2>What it cannot see</h2>
          <span className="kicker">The public pages, and no more</span>
        </div>
        <p className="footnote" style={{ margin: 0, maxWidth: "70ch" }}>
          It reads what a visitor who has not signed in reads. A screen answers
          with its public sample and the true count at every stage; the full
          lists, the gamma board below its first rows, and the other subscriber
          pages stay on the site. A subscriber&rsquo;s connection would have to
          know who is asking, and this version does not ask. It changes nothing
          and holds nothing: every question is answered from last night&rsquo;s
          published edition and forgotten.
        </p>
        <p className="footnote" style={{ margin: 0, maxWidth: "70ch" }}>
          The figures are end-of-day, from the last completed session. The
          earnings reactions are read twice a day from delayed quotes. A stock
          on a screen matches a shape, which is a description and not a
          prediction, and nothing an AI tells you from these pages is
          investment advice. Which sources were short on a given night is on
          the <Link href="/colophon" style={{ textDecoration: "underline" }}>colophon</Link>,
          and the AI is told the same.
        </p>
      </section>

      <section className="stack" style={{ gap: "var(--gap-md)" }}>
        <div className="ruled-head">
          <h2>Things to ask</h2>
          <span className="kicker">In your own words</span>
        </div>
        <ul className="footnote stack" style={{ margin: 0, paddingLeft: "1.2em", gap: "var(--gap-xs)",
                                               maxWidth: "70ch" }}>
          {QUESTIONS.map((question) => <li key={question}>{question}</li>)}
        </ul>
      </section>
    </div>
  );
}
