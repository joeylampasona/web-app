-- Scheduled economic data releases from FRED.
--
-- Cached so that publish never has to reach the network, and so a day FRED is
-- unreachable keeps the schedule we already had rather than emptying the tab.
-- Keyed on (date, release_id) because a release recurs and only its date makes
-- an occurrence distinct.
CREATE TABLE IF NOT EXISTS econ_releases (
  date        TEXT    NOT NULL,
  release_id  INTEGER NOT NULL,
  name        TEXT    NOT NULL,
  notable     INTEGER NOT NULL DEFAULT 0,
  fetched_at  TEXT    NOT NULL,
  PRIMARY KEY (date, release_id)
);

CREATE INDEX IF NOT EXISTS econ_releases_date_idx ON econ_releases (date);
