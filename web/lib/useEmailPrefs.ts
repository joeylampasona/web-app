"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./auth";
import { client } from "./supabase";

/**
 * Whether this account wants the weekly email.
 *
 * Reads and writes one row through the anon key, which row-level security
 * confines to the signed-in person. The sending job does not come through
 * here; it uses a service-role key in CI and never touches the browser.
 *
 * Turning it on records the moment. An account is not consent, and if anyone
 * ever asks whether there was permission, the answer has to be a row rather
 * than a recollection.
 */
export interface EmailPrefs {
  ready: boolean;
  weeklyDigest: boolean;
  saving: boolean;
  error: string | null;
  /** Null when the table has not been set up on this project yet. */
  configured: boolean;
  setWeeklyDigest: (on: boolean) => void;
}

export function useEmailPrefs(): EmailPrefs {
  const { signedIn, user, ready: authReady } = useAuth();
  const [weeklyDigest, setWeekly] = useState(false);
  const [ready, setReady] = useState(false);
  const [configured, setConfigured] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authReady) return;
    if (!signedIn || !user) { setReady(true); return; }
    const supabase = client();
    if (!supabase) { setReady(true); return; }

    let cancelled = false;
    void (async () => {
      const { data, error: readError } = await supabase
        .from("email_prefs")
        .select("weekly_digest")
        .eq("user_id", user.id)
        .maybeSingle();
      if (cancelled) return;
      if (readError) {
        // The table is added by a schema run. Until that has happened the
        // setting says so rather than showing a switch that cannot save.
        setConfigured(false);
        setError(readError.message);
      } else {
        setWeekly(Boolean(data?.weekly_digest));
      }
      setReady(true);
    })();
    return () => { cancelled = true; };
  }, [authReady, signedIn, user]);

  const setWeeklyDigest = useCallback((on: boolean) => {
    const supabase = client();
    if (!supabase || !user) return;
    setSaving(true);
    setError(null);
    void (async () => {
      const { error: writeError } = await supabase
        .from("email_prefs")
        .upsert({
          user_id: user.id,
          email: user.email,
          weekly_digest: on,
          // Only stamped when switching on. Switching off is not a consent
          // event and must not look like one.
          ...(on ? { consented_at: new Date().toISOString(), disabled_at: null } : {}),
        }, { onConflict: "user_id" });
      setSaving(false);
      if (writeError) { setError(writeError.message); return; }
      // Only after the write lands. A switch that flips before the row is
      // saved is a switch that lies when the save fails.
      setWeekly(on);
    })();
  }, [user]);

  return { ready, weeklyDigest, saving, error, configured, setWeeklyDigest };
}
