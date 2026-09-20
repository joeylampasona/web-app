-- Gamma concentration per symbol, cached between the fetch and the publish.
--
-- The same split every other optional source here uses: the catalysts stage
-- reaches the network, publish never does. A rebuild of out/ must not depend on
-- Yahoo being up, and a night Yahoo throttles us should cost the names it
-- missed rather than every name — the reason the earnings cache in 008 exists,
-- and the same reason applies here.
--
-- The profile is stored as JSON rather than one row per strike. It is read
-- whole, written whole, and never queried by strike, so a table of levels would
-- be a join to reassemble something we always want in one piece. If a query
-- like "which names have the most gamma at a strike near spot" ever appears,
-- that is the point to normalise it, not before.
CREATE TABLE IF NOT EXISTS gamma_profiles (
    symbol     TEXT PRIMARY KEY,
    -- The session the profile describes, which is not the same as when it was
    -- fetched: open interest reaches us a day late, so a profile stored tonight
    -- generally describes the previous session's book. Both are kept so the
    -- site can say which.
    as_of      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS gamma_profiles_as_of_idx
    ON gamma_profiles (as_of);
