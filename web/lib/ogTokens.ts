import "server-only";
import fs from "node:fs";
import path from "node:path";

/**
 * The handful of colours the link-preview image needs, read from tokens.css.
 *
 * A generated image is a server-rendered PNG, so it cannot read a CSS variable
 * at paint time the way every other surface does. Writing the hex values here
 * would make this the second place a colour is defined, and the two would drift
 * the first time the palette moved. So the stylesheet is parsed instead, and
 * tokens.css stays the only file where a colour is written down.
 *
 * The dark palette is used deliberately: a link preview has no viewer theme to
 * follow, and the site ships dark.
 */
const TOKENS = path.join(process.cwd(), "styles", "tokens.css");

function read(): Record<string, string> {
  const css = fs.readFileSync(TOKENS, "utf8");
  // Only the first :root block — the later ones are the light theme.
  const root = css.slice(0, css.indexOf("[data-theme") > 0
    ? css.indexOf("[data-theme")
    : css.length);
  const out: Record<string, string> = {};
  for (const [, name, value] of root.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    if (!(name in out)) out[name] = value.trim();
  }
  return out;
}

/** The light theme's block, laid over the first one: a token the light theme
 *  does not restate (the brand fill, the faces) keeps its root value. */
function readPaper(): Record<string, string> {
  const css = fs.readFileSync(TOKENS, "utf8");
  const start = css.indexOf('[data-theme="light"]');
  const out = { ...read() };
  if (start < 0) return out;
  const end = css.indexOf("\n}", start);
  const block = css.slice(start, end > start ? end : css.length);
  const seen = new Set<string>();
  for (const [, name, value] of block.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    if (!seen.has(name)) { out[name] = value.trim(); seen.add(name); }
  }
  return out;
}

let cached: Record<string, string> | null = null;
let cachedPaper: Record<string, string> | null = null;

/**
 * The same lookup against the light palette, for the share cards.
 *
 * Those are set as the printed page, paper and ink, whoever is looking: a
 * card is posted into somebody else's feed, where there is no reader's theme
 * to follow, and the paper is what makes it recognisably this site's.
 */
export function paperToken(name: string): string {
  if (!cachedPaper) cachedPaper = readPaper();
  const value = cachedPaper[name];
  if (!value) {
    throw new Error(`tokens.css has no --${name} for the share cards to read.`);
  }
  return value;
}

export function token(name: string): string {
  if (!cached) cached = read();
  const value = cached[name];
  if (!value) {
    throw new Error(
      `tokens.css has no --${name}. The preview image reads its palette from ` +
      `the stylesheet so there is only one place a colour is written; a missing ` +
      `token should fail here rather than silently pick some other colour.`,
    );
  }
  return value;
}
