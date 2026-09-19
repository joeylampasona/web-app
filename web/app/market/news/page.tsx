import Link from "next/link";
import { DataBanner, NoData } from "@/components/DataBanner";
import { MarketCTA } from "@/components/MarketCTA";
import { NewsList } from "@/components/NewsList";
import { getMeta, getNews, hasData } from "@/lib/data";
import { SITE_NAME } from "@/lib/copy";

export const metadata = {
  title: `In the news — ${SITE_NAME}`,
  description:
    "Recent headlines for the names this site follows, newest first, linking to whoever published them.",
};

export default function NewsPage() {
  if (!hasData()) return <NoData />;
  const news = getNews();

  return (
    <div className="page">
      <DataBanner meta={getMeta()} />
      <div className="eyebrow">Market · what is being written</div>
      <h1>In the news</h1>
      <p className="muted footnote">
        Headlines filed against the names this site follows, newest first. The
        list is not ranked, scored or summarised — the order is the order they
        were published, which is the only ordering here that is a fact rather
        than an opinion about which story matters.
      </p>
      <p className="caption dim">
        Every headline links to the publisher. We do not host the articles, and
        one appearing here is not a view about the company.
      </p>
      <NewsList articles={news?.articles ?? []} />
      <MarketCTA />
    </div>
  );
}
