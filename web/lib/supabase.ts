"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * One browser client, created on first use.
 *
 * Both variables are absent in the repo and on any deploy that has not been
 * given a project, and that is a supported state: `client()` returns null,
 * `configured` is false, and the site runs exactly as it did before accounts
 * existed — gates closed, nothing pretending to save. Nothing here throws on a
 * missing variable, because the build must not depend on a private project.
 *
 * The anon key is public by design. It identifies the project, not a person;
 * every table is protected by row-level security keyed on the signed-in user,
 * so this key alone reads and writes nothing. The schema those policies live in
 * is `supabase/schema.sql`.
 */
const PROJECT_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const configured = Boolean(PROJECT_URL && ANON);

/** The project address, for the accounts check page. Public by design — it
 *  identifies the project, not a person. The key is never exported. */
export const projectUrl = PROJECT_URL ?? null;

/**
 * Whether the configured address is the project address and nothing else.
 *
 * Supabase's dashboard shows the REST endpoint — `<project>.supabase.co/rest/v1/`
 * — more prominently than the bare project address, and the two look alike. Set
 * the first and the client appends its own path to it, so sign-in posts to
 * `/rest/v1/auth/v1/otp` and the project answers "Invalid path specified in
 * request URL". Nothing about that error names the setting that caused it.
 */
export function projectUrlProblem(raw: string | null): string | null {
  if (!raw) return "No address is configured.";
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return "This is not a web address. It should look like "
      + "https://your-project.supabase.co";
  }
  if (parsed.protocol !== "https:") return "This must start with https://";
  if (parsed.pathname !== "/" || parsed.search || parsed.hash) {
    return `Everything after the address has to go: "${parsed.pathname}`
      + `${parsed.search}" does not belong here. The client adds its own path, `
      + `so it must be ${parsed.origin} and nothing more.`;
  }
  return null;
}

let cached: SupabaseClient | null = null;

export function client(): SupabaseClient | null {
  if (!configured) return null;
  if (!cached) {
    cached = createClient(PROJECT_URL!, ANON!, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        // Off deliberately. The automatic exchange swallows its own failure:
        // when it does not work, nothing throws and nothing fires, and the only
        // symptom is a page that waits and then gives up guessing. /auth/callback
        // does the exchange itself so the real reason can be shown.
        detectSessionInUrl: false,
        flowType: "pkce",
      },
    });
  }
  return cached;
}
