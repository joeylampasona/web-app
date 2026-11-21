"use client";

import { useState } from "react";
import { copyText, siteUrl } from "@/lib/share";
import { shareOrSave } from "@/lib/shareBlob";
import { CopyTextButton } from "./CopyTextButton";

/**
 * A page's own share row: the link, the words, and the card.
 *
 * Quiet, at the head of a page, for the pages that have a card of their own.
 * The link goes to the platform's share sheet where there is one and to the
 * clipboard where there is not. The card is the same picture the link
 * unfurls into, fetched from its address rather than drawn again here.
 */
export function SharePage({ path, title, card, text }: {
  /** The page's own path: "/market/breadth". */
  path: string;
  title: string;
  /** The card's address: "/share/breadth.png". */
  card: string;
  /** The card's facts as lines for a post, the address already last. */
  text: string;
}) {
  const [link, setLink] = useState<"idle" | "copied">("idle");
  const [saving, setSaving] = useState<"idle" | "working" | "saved" | "failed">("idle");
  const url = siteUrl(path);

  const share = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch (error) {
        // Closing the sheet is an answer, not a failure.
        if ((error as Error)?.name === "AbortError") return;
      }
    }
    if (await copyText(url)) {
      setLink("copied");
      setTimeout(() => setLink("idle"), 1800);
    }
  };

  const save = async () => {
    setSaving("working");
    const settle = (next: "saved" | "failed" | "idle") => {
      setSaving(next);
      if (next !== "idle") setTimeout(() => setSaving("idle"), 2000);
    };
    try {
      const response = await fetch(card);
      if (!response.ok) { settle("failed"); return; }
      const name = card.split("/").pop()?.split("?")[0] ?? "card.png";
      const done = await shareOrSave(await response.blob(), `the-tape-${name}`, { title, url });
      settle(done === "saved" ? "saved" : "idle");
    } catch {
      settle("failed");
    }
  };

  const button = { minHeight: 36, padding: "0 var(--pad-md)" } as const;
  return (
    <div className="row share-page" data-share-page
         style={{ gap: "var(--gap-xs)", flexWrap: "wrap", margin: "var(--gap-sm) 0" }}>
      <button type="button" className="control footnote" onClick={share} style={button}>
        {link === "copied" ? "Link copied" : "Share"}
      </button>
      <CopyTextButton text={text} />
      <button type="button" className="control footnote" onClick={save}
              disabled={saving === "working"} style={button}>
        {saving === "working" ? "Fetching…" : saving === "saved" ? "Card saved"
          : saving === "failed" ? "Could not fetch it" : "Save card"}
      </button>
    </div>
  );
}
