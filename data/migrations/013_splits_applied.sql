-- Splits already reconciled against the stored bars, so each is handled once.
--
-- Bars are fetched one session at a time and kept. A price fetched before a
-- split stays at its pre-split level for ever unless something goes back and
-- adjusts it, and nothing did: every stock that split after its history was
-- cached carried a false cliff at the split date.
CREATE TABLE IF NOT EXISTS splits_applied (
    symbol          TEXT NOT NULL,
    execution_date  TEXT NOT NULL,
    factor          REAL NOT NULL,   -- pre-split prices are multiplied by this
    outcome         TEXT NOT NULL,   -- adjusted | already_adjusted | too_small | no_bars
    bars            INTEGER NOT NULL DEFAULT 0,
    applied_at      TEXT NOT NULL,
    PRIMARY KEY (symbol, execution_date)
);
