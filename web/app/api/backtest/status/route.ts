import { NextResponse } from "next/server";
import { fetchResult } from "@/lib/backtestRemote";
import { getBacktestPresetIndex } from "@/lib/data";

export const dynamic = "force-dynamic";

/**
 * Has the workflow published this result yet?
 *
 * Deliberately dumb: it looks for the file and says yes or not yet. It does not
 * watch the run, because a run that failed and a run that has not finished look
 * the same from here, and claiming to know which would be a guess. The caller
 * gives up on the clock instead.
 */
export async function GET(request: Request) {
  const key = new URL(request.url).searchParams.get("key");
  if (!key || !/^[a-zA-Z0-9._-]{1,120}$/.test(key)) {
    return NextResponse.json({ error: "bad key" }, { status: 400 });
  }
  const asOf = getBacktestPresetIndex()?.as_of;
  if (!asOf) {
    return NextResponse.json(
      { error: "This deploy has no published data to test against." },
      { status: 503 },
    );
  }
  try {
    const result = await fetchResult(asOf, key);
    if (result) return NextResponse.json({ status: "ready", result });
    return NextResponse.json({ status: "pending", key });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 503 },
    );
  }
}
