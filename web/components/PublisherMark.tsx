/**
 * A small mark for a publisher, drawn locally.
 *
 * NOT a favicon. Hot-linking icons from publisher domains would mean every
 * reader's browser making a request to a dozen third parties on every page
 * load, which tells those third parties who is reading what. This site
 * currently makes no third-party requests at all, and a decorative icon is a
 * poor reason to be the first.
 *
 * So the mark is derived from the name: the initials, on a hue hashed from the
 * string. Deterministic, so the same publisher is always the same colour and
 * the eye can learn it, which is the actual job a favicon does in a list.
 */
const INITIAL_OVERRIDES: Record<string, string> = {
  "associated press": "AP",
  "the wall street journal": "WSJ",
  "investor's business daily": "IBD",
  "globenewswire": "GN",
  "business wire": "BW",
  "pr newswire": "PR",
  "seeking alpha": "SA",
};

function initials(publisher: string): string {
  const key = publisher.trim().toLowerCase();
  if (INITIAL_OVERRIDES[key]) return INITIAL_OVERRIDES[key];
  const words = publisher.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/** A stable hue per publisher. Not meaningful — just consistent. */
function hue(publisher: string): number {
  let hash = 0;
  for (let i = 0; i < publisher.length; i += 1) {
    hash = (hash * 31 + publisher.charCodeAt(i)) % 360;
  }
  return hash;
}

export function PublisherMark({ publisher }: { publisher: string }) {
  const text = initials(publisher);
  const h = hue(publisher);
  return (
    <span
      aria-hidden
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 16, height: 16, borderRadius: 3, flexShrink: 0,
        fontSize: text.length > 2 ? 7 : 8,
        fontWeight: 600, letterSpacing: "0.02em",
        // Low-saturation so a row of these reads as texture rather than as a
        // set of competing colour signals next to the real ones on the page.
        background: `hsl(${h} 30% 28% / 0.55)`,
        color: `hsl(${h} 45% 78%)`,
        border: "0.5px solid hsl(" + h + " 30% 40% / 0.5)",
      }}
    >
      {text}
    </span>
  );
}
