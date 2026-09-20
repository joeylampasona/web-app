import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

/**
 * Content only subscribers may read.
 *
 * The entitlement check is not here. This route takes the caller's own access
 * token, asks the database as that person, and returns whatever comes back —
 * so the decision is made by the row-level security policy on
 * `gated_content`, in Postgres, on every row.
 *
 * That is deliberate. A route that fetched with the service-role key and then
 * decided for itself who deserves the answer would be one forgotten `if` away
 * from serving everything to everybody, and it would be the only thing
 * standing between an anonymous request and the paid content. This way the
 * worst a bug in this file can do is fail to return something the caller was
 * already entitled to.
 *
 * A caller with no token, an expired one, or a live session but no
 * subscription all get the same answer: an empty result and 404. Not 403 —
 * "you may not have this" confirms the thing exists and that its path was
 * guessed correctly, and there is no reason to hand that out.
 */
export const dynamic = "force-dynamic";

const PROJECT_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Paths are keys in a table, not files on a disk, so directory traversal
// cannot escape anywhere — but an unbounded string still becomes a query
// parameter, and a shape this predictable costs nothing to require.
const PATH_SHAPE = /^[a-z0-9_-]+(\/[a-z0-9_.-]+)*\.json$/;

export async function GET(request: Request) {
  if (!PROJECT_URL || !ANON) {
    return NextResponse.json({ error: "not configured" }, { status: 503 });
  }

  const path = new URL(request.url).searchParams.get("path") ?? "";
  if (!PATH_SHAPE.test(path)) {
    return NextResponse.json({ error: "bad path" }, { status: 400 });
  }

  // The caller's own token, never the service-role key. Absent is fine and
  // falls through to the same empty answer as a valid token without a
  // subscription — the two are not distinguished on the way out.
  const authorization = request.headers.get("authorization") ?? "";

  const supabase = createClient(PROJECT_URL, ANON, {
    global: { headers: authorization ? { Authorization: authorization } : {} },
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const { data, error } = await supabase
    .from("gated_content")
    .select("payload, as_of, updated_at")
    .eq("path", path)
    .maybeSingle();

  if (error || !data) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  return NextResponse.json(
    { path, as_of: data.as_of, updated_at: data.updated_at, payload: data.payload },
    // Private: this is one person's entitlement, and a shared cache holding it
    // would serve it to the next person through the same edge.
    { headers: { "Cache-Control": "private, no-store" } },
  );
}
