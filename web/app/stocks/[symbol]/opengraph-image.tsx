import { ImageResponse } from "next/og";
import { token } from "@/lib/ogTokens";
import { getStock } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const runtime = "nodejs";
export const alt = `Stock on ${SITE_NAME}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/**
 * Sharing one ticker should preview that ticker, not the site.
 *
 * No chart: a preview is read at a glance and at thumbnail size, where a
 * hundred candles are a smudge. The name, the price, the stage and the ranking
 * are what survive being shrunk, so those are what it carries.
 */
export default async function Image({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const stock = getStock(symbol.toUpperCase());
  const setup = stock?.primary_setup ?? null;
  const last = stock?.bars?.[stock.bars.length - 1]?.close ?? null;
  const ranked = typeof stock?.rs_rating === "number";
  const facts = [
    last !== null ? `$${last.toFixed(2)}` : "",
    `RS ${ranked ? stock!.rs_rating : "not ranked yet"}`,
    stock?.industry ?? "",
  ].filter(Boolean);

  return new ImageResponse(
    (
      <div style={{
        width: "100%", height: "100%", display: "flex", flexDirection: "column",
        justifyContent: "space-between", background: token("surface-0"),
        padding: 72, fontFamily: "sans-serif",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 22, height: 22, borderRadius: 5,
                        background: token("brand") }} />
          <div style={{ fontSize: 26, color: token("text-muted") }}>
            {SITE_NAME}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ fontSize: 30, color: token("text-muted"), letterSpacing: 2 }}>
            {symbol.toUpperCase()}
          </div>
          <div style={{ fontSize: 66, color: token("text-primary"), lineHeight: 1.1,
                        maxWidth: 1000 }}>
            {stock?.name ?? symbol.toUpperCase()}
          </div>
          <div style={{ display: "flex", gap: 28, fontSize: 30,
                        color: token("text-secondary"), marginTop: 8 }}>
            {facts.map((fact) => <div key={fact}>{fact}</div>)}
          </div>
          {setup && (
            <div style={{ display: "flex", marginTop: 14 }}>
              <div style={{ fontSize: 26, color: token("on-brand"),
                            background: token("brand"), padding: "10px 22px",
                            borderRadius: 999 }}>
                {`${setup.screen.replace(/_/g, " ")} · ${setup.stage.replace(/_/g, " ")}`}
              </div>
            </div>
          )}
        </div>

        <div style={{ fontSize: 23, color: token("text-muted"),
                      borderTop: `1px solid ${token("border")}`, paddingTop: 22 }}>
          A screening and market-analytics tool. Not investment advice.
          Historical figures are hypothetical.
        </div>
      </div>
    ),
    size,
  );
}
