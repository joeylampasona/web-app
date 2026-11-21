/**
 * Where a shared thing points, and how its words are put on a clipboard.
 *
 * The origin is written out rather than read from the window: text copied on
 * a preview deployment or a local build is still going to be pasted somewhere
 * public, and it should send people to the site, not to the place it was
 * copied from.
 */
export const SITE_ORIGIN = "https://thetape.cc";

export function siteUrl(path: string): string {
  return `${SITE_ORIGIN}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Lines for a post, the page's address last. Blank lines are dropped. */
export function postText(lines: (string | null | undefined | false)[], path: string): string {
  const kept = lines.map((line) => (line || "").trim()).filter(Boolean);
  return [...kept, siteUrl(path)].join("\n");
}

/** True when the text reached the clipboard. Never throws. */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // A page without clipboard permission still has the old way.
    try {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      const done = document.execCommand("copy");
      area.remove();
      return done;
    } catch {
      return false;
    }
  }
}
