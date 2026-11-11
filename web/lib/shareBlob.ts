"use client";

/**
 * Hand an image to the reader: the platform's share sheet where it takes a
 * file (a phone), a download where it does not (most desktop browsers).
 * Returns what happened so the button can say so.
 */
export async function shareOrSave(blob: Blob, filename: string,
                                  meta: { title: string; url?: string }): Promise<"shared" | "saved"> {
  const file = new File([blob], filename, { type: "image/png" });
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: meta.title, url: meta.url });
      return "shared";
    } catch (error) {
      // Closing the share sheet is not a failure, and needs no download.
      if ((error as Error)?.name === "AbortError") return "shared";
    }
  }
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(href);
  return "saved";
}
