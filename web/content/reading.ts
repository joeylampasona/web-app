/**
 * The article layout itself is an open question in the brief, so this is the
 * index only. Each entry is a real thing we can say honestly about the method;
 * none of them are written yet, and the cards say so rather than linking to a
 * page that does not exist.
 */
export interface Article {
  slug: string;
  kind: "guide" | "case_study";
  title: string;
  excerpt: string;
  date: string;
  status: "planned";
}

export const ARTICLES: Article[] = [
  {
    slug: "what-relative-strength-measures",
    kind: "guide",
    title: "What relative strength actually measures",
    excerpt:
      "A 1-99 ranking of three return windows against the benchmark, and why a " +
      "rating of 92 says something about the past twelve months rather than the " +
      "next twelve.",
    date: "2026-09-01",
    status: "planned",
  },
  {
    slug: "reading-a-base",
    kind: "guide",
    title: "Reading a base without reading too much into it",
    excerpt:
      "Depth, duration and the pivot are descriptions of what a stock has done. " +
      "Here is how to use them for timing without treating the shape as a forecast.",
    date: "2026-08-18",
    status: "planned",
  },
  {
    slug: "why-played-out-is-published",
    kind: "guide",
    title: "Why we publish the ones that did not work",
    excerpt:
      "The played-out bucket is usually the biggest one on the page. Hiding it " +
      "would make every other number on the site unfalsifiable.",
    date: "2026-08-04",
    status: "planned",
  },
  {
    slug: "vcp-out-of-sample",
    kind: "case_study",
    title: "Our own VCP study came back negative out of sample",
    excerpt:
      "The structural components carried no measurable edge. Relative strength " +
      "did, at p=0.006. What we changed about this site as a result.",
    date: "2026-07-21",
    status: "planned",
  },
  {
    slug: "survivorship",
    kind: "case_study",
    title: "What a survivorship-biased backtest is worth",
    excerpt:
      "Free data carries no delisted companies. We measured how much that " +
      "flatters a breakout test, and why every figure ships with a provisional flag.",
    date: "2026-07-07",
    status: "planned",
  },
];
