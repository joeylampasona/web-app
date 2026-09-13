import { NextResponse } from "next/server";
import { EAGER_CHARTS, barsFor, getBreakouts } from "@/lib/data";

export const dynamic = "force-dynamic";

export function GET(request: Request) {
  const date = new URL(request.url).searchParams.get("date") ?? "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json({ error: "bad date" }, { status: 400 });
  }
  const file = getBreakouts(date);
  if (!file) return NextResponse.json({ setups: [], bars: {} });
  return NextResponse.json({
    setups: file.setups,
    bars: barsFor(file.setups.map((s) => s.symbol).slice(0, EAGER_CHARTS)),
  });
}
