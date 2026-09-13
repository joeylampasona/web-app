"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./auth";
import { client } from "./supabase";

export const MAX_SCREENS = 20;

export interface SavedScreen {
  id: string;
  name: string;
  /** Which detector the dials belong to — dials are not portable between them. */
  screen: string;
  values: Record<string, number | boolean>;
  created_at: string;
}

/**
 * A saved screen is a detector plus the position of every dial. It is stored
 * against the account rather than re-derived, so a screen keeps working when
 * the published defaults move under it.
 *
 * The dial values are stored as JSON exactly as the panel holds them. Keys that
 * no longer exist in a later version of the detector are ignored on load rather
 * than resetting the whole screen, so an old save degrades to the dials it can
 * still fill.
 */
export function useSavedScreens() {
  const { signedIn, user, requireSignUp } = useAuth();
  const [screens, setScreens] = useState<SavedScreen[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const supabase = client();
    if (!signedIn || !supabase) { setScreens([]); return; }
    setLoading(true);
    const { data, error: readError } = await supabase
      .from("saved_screens")
      .select("id, name, screen, values, created_at")
      .order("created_at", { ascending: false });
    setLoading(false);
    if (readError) { setError(readError.message); return; }
    setError(null);
    setScreens((data ?? []) as SavedScreen[]);
  }, [signedIn]);

  useEffect(() => { void load(); }, [load]);

  const save = useCallback(
    async (name: string, screen: string, values: Record<string, number | boolean>) => {
      if (!signedIn || !user) {
        requireSignUp("Save this screen");
        return false;
      }
      const supabase = client();
      if (!supabase) return false;
      const label = name.trim();
      if (!label) { setError("Give the screen a name first."); return false; }
      if (screens.length >= MAX_SCREENS) {
        setError(`That is ${MAX_SCREENS} screens, the limit. Delete one to save another.`);
        return false;
      }
      const { error: writeError } = await supabase
        .from("saved_screens")
        .insert({ user_id: user.id, name: label, screen, values });
      if (writeError) {
        // 23505 is the unique index on (user_id, name). The database says
        // "duplicate key value violates unique constraint"; a reader who has
        // reused a name needs to be told that, in those words.
        setError(
          writeError.code === "23505"
            ? `You already have a screen called “${label}”. Pick another name.`
            : writeError.message,
        );
        return false;
      }
      setError(null);
      await load();
      return true;
    },
    [load, requireSignUp, screens.length, signedIn, user],
  );

  const remove = useCallback(
    async (id: string) => {
      const supabase = client();
      if (!supabase) return;
      const { error: deleteError } = await supabase
        .from("saved_screens").delete().eq("id", id);
      if (deleteError) { setError(deleteError.message); return; }
      setScreens((held) => held.filter((s) => s.id !== id));
    },
    [],
  );

  return { signedIn, screens, save, remove, loading, error, full: screens.length >= MAX_SCREENS };
}
