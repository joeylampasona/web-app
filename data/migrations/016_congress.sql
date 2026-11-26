-- Trades by members of the House, from the periodic transaction reports the
-- Clerk publishes. See data/congress.py.
--
-- congress_filings is every report asked about, whatever came of it: read,
-- a scanned paper filing with no text, or a file the Clerk does not have.
-- It is what stops a report being fetched every night. A report that did
-- not answer is not recorded, so it is asked about again.
CREATE TABLE IF NOT EXISTS congress_filings (
    doc_id        TEXT PRIMARY KEY,
    year          INTEGER NOT NULL,
    member        TEXT NOT NULL,
    district      TEXT NOT NULL DEFAULT '',
    filed         TEXT NOT NULL,
    status        TEXT NOT NULL,            -- read | no_text | missing
    transactions  INTEGER NOT NULL DEFAULT 0,
    read_at       TEXT NOT NULL
);

-- One row a transaction, keyed by the report and its place in it, so a
-- report read twice replaces its rows and never doubles them. Every asset
-- type is kept; only stocks with a ticker are published.
CREATE TABLE IF NOT EXISTS congress_trades (
    doc_id       TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    year         INTEGER NOT NULL,
    member       TEXT NOT NULL,
    district     TEXT NOT NULL DEFAULT '',
    ticker       TEXT,
    asset        TEXT NOT NULL DEFAULT '',
    kind         TEXT NOT NULL DEFAULT '',  -- the form's asset type code: ST, GS, OP ...
    type         TEXT NOT NULL,             -- buy | sell | partial sale | exchange
    owner        TEXT,                      -- self | spouse | joint | child | NULL unknown
    traded       TEXT,
    notified     TEXT,
    filed        TEXT NOT NULL,
    amount_low   INTEGER,
    amount_high  INTEGER,
    amount_text  TEXT NOT NULL DEFAULT '',
    amended      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (doc_id, seq)
);
CREATE INDEX IF NOT EXISTS congress_trades_ticker_idx ON congress_trades (ticker, traded DESC);
