import type { Metadata } from "next";
import { SITE_NAME } from "@/lib/copy";
import { CARD } from "./base";

/**
 * A page's link preview: its own title, a sentence, and its own card.
 *
 * The layout names one supplied banner for every page, and a page that sets
 * any preview field replaces that whole block rather than adding to it, so
 * everything a preview needs is restated here once for all of them.
 *
 * `version` is the session the card was drawn for. Sites that show previews
 * keep a picture by its address, and without it a link pasted tonight would
 * show whichever night that site first saw.
 */
export function cardMetadata({ title, description, card, version }: {
  title: string;
  description: string;
  /** The card's address, as served: "/share/breadth.png". */
  card: string;
  version?: string | null;
}): Metadata {
  const image = version ? `${card}?v=${version}` : card;
  const full = title.includes(SITE_NAME) ? title : `${title} — ${SITE_NAME}`;
  return {
    title: full,
    description,
    openGraph: {
      type: "website", siteName: SITE_NAME, title: full, description,
      images: [{ url: image, ...CARD, alt: title }],
    },
    twitter: { card: "summary_large_image", title: full, description, images: [image] },
  };
}
