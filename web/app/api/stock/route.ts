import { NextResponse } from "next/server";
import { getStock } from "@/lib/data";

export const dynamic = "force-dynamic";

export function GET(request: Request) {
  const symbol = new URL(request.url).searchParams.get("symbol") ?? "";
  if (!/^[A-Za-z.\-]{1,8}$/.test(symbol)) {
    return NextResponse.json({ error: "bad symbol" }, { status: 400 });
  }
  const stock = getStock(symbol);
  if (!stock) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(stock);
}
