-- Each night's front page, kept.
--
-- The published tree is rebuilt and force-pushed whole every night, so nothing
-- in it survives to the next one: yesterday's read was gone the moment
-- tonight's was written. An edition is the small part of a night worth paging
-- back to (the read, its four checks, where strength sat, the breadth strip),
-- stored here so the archive can be written out again in full each night.
CREATE TABLE IF NOT EXISTS editions (
    date        TEXT PRIMARY KEY,
    body        TEXT NOT NULL,       -- the edition as JSON
    rebuilt     INTEGER NOT NULL DEFAULT 0,  -- 1 when recomputed from history, not kept on the night
    written_at  TEXT NOT NULL
);
