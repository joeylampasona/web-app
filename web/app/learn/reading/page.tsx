import { ReadingList } from "@/components/ReadingList";
import { ARTICLES } from "@/content/reading";

export default function ReadingPage() {
  return (
    <div className="page">
      <div className="eyebrow">Learn · reading</div>
      <h1 style={{ marginBottom: "var(--gap-sm)" }}>Reading</h1>
      <p className="muted footnote">
        The index is here; the article pages are not built yet, and the layout for
        them is still an open question rather than an oversight.
      </p>
      <ReadingList articles={ARTICLES} />
    </div>
  );
}
