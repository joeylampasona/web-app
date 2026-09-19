-- Earnings dates, cached.
--
-- They come from a per-ticker scrape of an undocumented Yahoo endpoint: two
-- thousand requests a night, which Yahoo rate-limits. Last night's run logged
-- "Crumb fetch rate-limited (HTTP 429)" and 62% of stock pages published an
-- empty catalyst roadmap — for companies that certainly report inside the
-- ninety-day window.
--
-- Nothing was stored, so a throttled night lost everything it could not fetch
-- and the next night started from zero. Which pages were empty changed nightly.
--
-- A date a company has announced does not change often, so it is worth keeping.
-- With this, coverage accumulates across runs instead of resetting: a night
-- that only manages four hundred names keeps the other sixteen hundred from
-- the nights before.
CREATE TABLE IF NOT EXISTS earnings_dates (
    symbol     TEXT NOT NULL,
    date       TEXT NOT NULL,
    -- "confirmed" when the company has announced it, "tentative" when the
    -- source is projecting from reporting history. The site says which.
    confirmed  TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS earnings_dates_symbol_idx
    ON earnings_dates (symbol, date);
