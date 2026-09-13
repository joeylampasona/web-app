-- Headlines, by ticker.
--
-- Stored rather than fetched at read time: the provider's free tier allows five
-- calls a minute, and a page that fetched its own news would spend that budget
-- on one reader. The nightly fills this; the site only ever reads it.
--
-- Headline, publisher, timestamp and a link out. Never the article body — that
-- belongs to whoever wrote it.

CREATE TABLE IF NOT EXISTS news (
    article_id    TEXT NOT NULL,      -- the provider's id, so re-runs are idempotent
    symbol        TEXT NOT NULL,
    published_at  TEXT NOT NULL,      -- ISO 8601 UTC
    title         TEXT NOT NULL,
    publisher     TEXT NOT NULL,
    url           TEXT NOT NULL,
    fetched_at    TEXT NOT NULL,
    PRIMARY KEY (article_id, symbol)
);

CREATE INDEX IF NOT EXISTS news_symbol_idx ON news (symbol, published_at DESC);
CREATE INDEX IF NOT EXISTS news_published_idx ON news (published_at DESC);
