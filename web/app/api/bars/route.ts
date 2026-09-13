import { NextResponse } from "next/server";
import { barsFor } from "@/lib/data";

export const dynamic = "force-dynamic";

// One screen can hold nearly three hundred cards. Sending every chart with the
// page made /screens/vcp a 5MB download, most of it for cards nobody scrolls
// to. Cards ask for their own chart when they come into view instead, and this
// is what answers them.
const MAX = 60;

export async function GET(request: Request) {
  const raw = new URL(request.url).searchParams.get("symbols") ?? "";
  const symbols = raw.split(",")
    .map((s) => s.trim().toUpperCase())
    .filter((s) => /^[A-Z][A-Z0-9.-]{0,11}$/.test(s))
    .slice(0, MAX);

  if (!symbols.length) {
    return NextResponse.json({ error: "no symbols" }, { status: 400 });
  }
  return NextResponse.json(
    { bars: barsFor(symbols) },
    // Prices change once a day. A card re-entering the viewport should not
    // re-fetch, and neither should a second reader on the same deployment.
    { headers: { "Cache-Control": "public, max-age=300, s-maxage=3600" } },
  );
}
