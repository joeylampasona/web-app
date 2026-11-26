-- How much traded in each company's options, a row a session.
--
-- The nightly already downloads every contract for gamma; this keeps what it
-- says about the day's volume. A row a session rather than one row a company,
-- unlike gamma_profiles: the question "is this a lot for this company" needs
-- the company's own earlier days, and they are cheap to keep (a few hundred
-- bytes a night, pruned after 45 days).
--
-- `volume` is repeated out of the payload so the usual day can be averaged
-- without parsing every stored payload.
CREATE TABLE IF NOT EXISTS options_volume (
    symbol     TEXT NOT NULL,
    as_of      TEXT NOT NULL,
    volume     INTEGER NOT NULL DEFAULT 0,
    payload    TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (symbol, as_of)
);

CREATE INDEX IF NOT EXISTS options_volume_as_of_idx
    ON options_volume (as_of);
