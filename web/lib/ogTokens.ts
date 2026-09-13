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

let cached: Record<string, string> | null = null;

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
