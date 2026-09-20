-- Analyst price targets and estimates, cached.
--
-- Same shape and the same reason as the earnings cache in 008: a per-ticker
-- scrape of an undocumented Yahoo endpoint that rate-limits, where a throttled
-- night must cost the names it missed rather than all of them.
--
-- The payload is stored whole as JSON. It is read whole, written whole, and
-- never queried by field — the page wants one company's forecast at a time —
-- so columns here would be a schema to migrate every time Yahoo adds a period.
CREATE TABLE IF NOT EXISTS forecasts (
    symbol     TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    -- When we asked, not when the analysts wrote it. The page shows the age so
    -- a target from last Tuesday is not read as today's view.
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS forecasts_fetched_idx ON forecasts (fetched_at);
