import { ImageResponse } from "next/og";
import { TAGLINE } from "@/lib/copy";
import { token } from "@/lib/ogTokens";
import { getMeta } from "@/lib/data";

export const runtime = "nodejs";
export const alt = "Base & Breakout — bases, breakouts and relative strength";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/**
 * What a shared link looks like before anyone clicks it.
 *
 * Without this a link to the site renders as a grey rectangle with a domain in
 * it, which is the same problem the share button had and was fixed there by
 * sending an image. This is the equivalent for a pasted URL.
 *
 * The palette is read from tokens.css rather than written here, so this does
 * not become a second place a colour is defined.
 */
export default async function Image() {
  const meta = getMeta();
  const total = meta?.screens?.reduce((sum, s) => sum + (s.total ?? 0), 0) ?? 0;
  // Satori needs a single child per element unless it is explicitly flex, so
  // the line is composed here rather than assembled from fragments in the JSX.
  const subtitle = meta?.universe_count
    ? [
        `${meta.universe_count.toLocaleString()} liquid US stocks scanned`,
        total > 0 ? `${total.toLocaleString()} setups on six screens` : "",
        meta.as_of ?? "",
      ].filter(Boolean).join(" · ")
    : "";

  return new ImageResponse(
    (
      <div style={{
        width: "100%", height: "100%", display: "flex", flexDirection: "column",
        justifyContent: "space-between", background: token("surface-0"),
        padding: 72, fontFamily: "sans-serif",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ width: 28, height: 28, borderRadius: 6,
                        background: token("brand") }} />
          <div style={{ fontSize: 34, color: token("text-primary"), fontWeight: 500 }}>
            Base &amp; Breakout
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ fontSize: 62, color: token("text-primary"), lineHeight: 1.15,
                        maxWidth: 940 }}>
            {TAGLINE}
          </div>
          {subtitle ? (
            <div style={{ fontSize: 30, color: token("text-secondary") }}>{subtitle}</div>
          ) : null}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between",
                      alignItems: "flex-end", borderTop: `1px solid ${token("border")}`,
                      paddingTop: 24 }}>
          <div style={{ fontSize: 24, color: token("text-muted"), maxWidth: 820 }}>
            A screening and market-analytics tool. Not investment advice.
          </div>
          <div style={{ fontSize: 24, color: token("brand") }}>base-and-breakout</div>
        </div>
      </div>
    ),
    size,
  );
}
