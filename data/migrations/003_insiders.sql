-- Insider transactions from SEC Form 4, and the filings we have already read.
--
-- A filing never changes once it is filed, so both tables are a permanent
-- cache: the nightly asks SEC only for filings it has not seen. Without this,
-- every run would re-read years of the same XML at ten requests a second.

CREATE TABLE IF NOT EXISTS insider_filings (
    accession    TEXT PRIMARY KEY,     -- SEC's id for the filing
    symbol       TEXT NOT NULL,
    filed_at     TEXT NOT NULL,        -- ISO date SEC recorded it
    fetched_at   TEXT NOT NULL,
    -- A filing we read and found nothing reportable in is still a filing we
    -- read. Recorded so it is never fetched twice.
    parsed       INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS insider_filings_symbol_idx
    ON insider_filings (symbol, filed_at DESC);

CREATE TABLE IF NOT EXISTS insider_transactions (
    accession    TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    traded_at    TEXT NOT NULL,
    owner        TEXT NOT NULL,
    role         TEXT NOT NULL,        -- CEO, Director, 10% owner, ...
    -- SEC's transaction code. P and S are someone deciding to buy or sell;
    -- A, M, F and G are compensation mechanics and are kept separate because
    -- reporting them as "insider selling" is how that number gets misread.
    code         TEXT NOT NULL,
    shares       REAL,
    price        REAL,
    value        REAL,
    direction    TEXT NOT NULL,        -- 'buy' or 'sell'
    PRIMARY KEY (accession, symbol, traded_at, owner, code, shares)
);

CREATE INDEX IF NOT EXISTS insider_transactions_symbol_idx
    ON insider_transactions (symbol, traded_at DESC);
