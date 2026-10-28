-- Three more blocks from the Market Desk feed, and fundamentals per company.
--
-- market_context (desk schema 1.6): CBOE put/call ratios and the desk's
-- regime label, each with its own date. earnings_iv (1.7): the move the
-- options price into a report against what the stock usually does, and how
-- often the priced move held. holders (1.7): the desk's tracked funds' 13F
-- positions per ticker. Stored whole as JSON, like edge and positioning.
-- holders is about half a megabyte, so only the newest run keeps its copy;
-- older rows are emptied when a new one lands.
ALTER TABLE desk_runs ADD COLUMN market_context TEXT NOT NULL DEFAULT 'null';
ALTER TABLE desk_runs ADD COLUMN earnings_iv TEXT NOT NULL DEFAULT 'null';
ALTER TABLE desk_runs ADD COLUMN holders TEXT NOT NULL DEFAULT 'null';

-- Trailing-twelve-month figures from each company's own XBRL filings
-- (data/fundamentals.py). payload is null when SEC had nothing usable, which
-- is stored too, so a foreign filer is not asked again every night.
CREATE TABLE IF NOT EXISTS fundamentals_xbrl (
  symbol     TEXT PRIMARY KEY,
  fetched_at TEXT NOT NULL,
  payload    TEXT NOT NULL DEFAULT 'null'
);
