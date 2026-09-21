"use client";

import { Locked } from "@/components/Locked";
import { ScreenBrowser } from "@/components/ScreenBrowser";
import { useGated } from "@/lib/useGated";
import type { Bar, ScreenFile } from "@/lib/types";

/**
 * A screen: a sample of each stage, or the whole list.
 *
 * Ten names per stage, so no tab runs past ten charts, and none at all of the
 * forming stage. Forming is the list of bases before they break — the only
 * stage where seeing it early is worth anything, since the other three
 * describe something that has already happened. A sample of those shows what
 * the site does; a sample of forming would be the thing itself.
 *
 * Every stage keeps its true count whether the rows are there or not, so the
 * forming tab reads "144" and then explains itself. An empty list under a
 * count of 144 would read as a fault.
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

  const lockedStages = file.locked_stages ?? [];
  const shown = Object.values(file.setups).reduce((n, rows) => n + rows.length, 0);
  const checking = full.state === "loading";

  const offer = checking ? (
    <p className="caption dim">Checking your subscription…</p>
  ) : (
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
  );

  // The same offer in two places, and it has to be: inside the forming tab,
  // where there is nothing else to show, and under the others, where there is
  // a sample above it.
  return (
    <>
      <ScreenBrowser file={file} bars={bars}
                     lockedStages={lockedStages}
                     lockedPanel={offer} />
      {shown < file.total && (
        <div style={{ marginTop: "var(--gap-md)" }}>{offer}</div>
      )}
    </>
  );
}
