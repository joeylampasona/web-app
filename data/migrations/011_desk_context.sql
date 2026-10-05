-- Two things the Market Desk feed carries per run beyond its signals.
--
-- edge: the desk's own scorecard, one row per signal type, measured against
-- random unflagged names over 90 days. Stored so each signal on a stock page
-- can say whether its type has worked, instead of reading as a recommendation
-- the desk's own numbers contradict.
--
-- positioning: CFTC Commitments of Traders, the desk's weekly table (schema
-- 1.5). Null on runs from before 1.5 and before the first report.
--
-- Both stored whole as JSON and read whole, as the forecasts are: nothing
-- queries them by field, and columns would be a migration every time the
-- desk adds one within its major version.
ALTER TABLE desk_runs ADD COLUMN edge TEXT NOT NULL DEFAULT '[]';
ALTER TABLE desk_runs ADD COLUMN positioning TEXT NOT NULL DEFAULT 'null';
