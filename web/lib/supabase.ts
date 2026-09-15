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
const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const configured = Boolean(URL && ANON);

/** The project address, for the accounts check page. Public by design — it
 *  identifies the project, not a person. The key is never exported. */
export const projectUrl = URL ?? null;

let cached: SupabaseClient | null = null;

export function client(): SupabaseClient | null {
  if (!configured) return null;
  if (!cached) {
    cached = createClient(URL!, ANON!, {
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
