"use client";

import { Locked } from "@/components/Locked";
import { ScreenBrowser } from "@/components/ScreenBrowser";
import { useGated } from "@/lib/useGated";
import type { Bar, ScreenFile } from "@/lib/types";

/**
 * A screen: a sample of each stage, or the whole list.
 *
 * Fresh breakouts are never trimmed. That stage is the daily feed, it is
 * published separately for the home page anyway, and it is how the site is
 * found — putting it behind a wall would gate the front door.
 *
 * Every stage keeps its true count whether or not the rows are there, so the
 * page says what it is withholding. That is `stage_counts`, which the publisher
 * leaves alone deliberately.
 */
export function GatedScreenBrowser({
  file,
  bars,
}: {
  file: ScreenFile;
  bars: Record<string, Bar[]>;
}) {
  const gated = Boolean(file.gated);
  const full = useGated<ScreenFile>(gated ? `screens/${file.screen}.json` : null);

  if (!gated) return <ScreenBrowser file={file} bars={bars} />;

  if (full.state === "ready" && full.data?.setups) {
    // The gated document is the same file, whole. Rendering from it rather
    // than merging the withheld rows into the public head means the list can
    // never be half of one run and half of another.
    return <ScreenBrowser file={{ ...file, setups: full.data.setups }} bars={bars} />;
  }

  const shown = Object.values(file.setups).reduce((n, rows) => n + rows.length, 0);

  return (
    <>
      <ScreenBrowser file={file} bars={bars} />
      {full.state === "loading" ? (
        <p className="caption dim" style={{ marginTop: "var(--gap-md)" }}>
          Checking your subscription…
        </p>
      ) : shown < file.total ? (
        <div style={{ marginTop: "var(--gap-md)" }}>
          <Locked
            what={`The rest of the ${file.name} list, at every stage,`}
            shown={shown}
            total={file.total}
          >
            {full.state === "error" && (
              <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
                The subscription check did not answer ({full.detail}).
              </p>
            )}
          </Locked>
        </div>
      ) : null}
    </>
  );
}
