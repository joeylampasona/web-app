-- Signals ingested from the Market Desk repository.
--
-- That project sweeps the whole US market overnight for filings, insider
-- clusters, tape anomalies and sentiment, and writes signals/YYYY-MM-DD.json
-- against a documented, versioned contract. This is where those land.
--
-- Kept in its own tables rather than merged into ours: it is a different
-- system's judgement, it has its own schema version, and when it is wrong we
-- want to be able to say which source said so.

CREATE TABLE IF NOT EXISTS desk_signals (
    as_of      TEXT NOT NULL,        -- the desk's scan date
    symbol     TEXT NOT NULL,
    source     TEXT NOT NULL,        -- FILING | INSIDER | TAPE | SENTIMENT | EVENT
    reason     TEXT NOT NULL,        -- CLUSTER_BUY, RED_FLAG, 13D_ACTIVIST, ...
    detail     TEXT NOT NULL DEFAULT '',
    magnitude  REAL,
    url        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (as_of, symbol, source, reason, detail)
);

CREATE INDEX IF NOT EXISTS desk_signals_symbol_idx ON desk_signals (symbol, as_of DESC);

CREATE TABLE IF NOT EXISTS desk_earnings (
    symbol       TEXT PRIMARY KEY,
    report_date  TEXT NOT NULL,
    -- bmo (before open), amc (after close), or empty when the desk does not
    -- know. Empty is not "during the session" — it is unknown, and the site
    -- has to say so rather than pick one.
    hour         TEXT NOT NULL DEFAULT '',
    as_of        TEXT NOT NULL
);

-- One row per run: which scanners worked. An empty TAPE set means nothing at
-- all if the tape scanner failed, and this is what tells the two apart.
CREATE TABLE IF NOT EXISTS desk_runs (
    as_of         TEXT PRIMARY KEY,
    generated_at  TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    universe_size INTEGER,
    stage_status  TEXT NOT NULL DEFAULT '{}',
    fetched_at    TEXT NOT NULL
);
