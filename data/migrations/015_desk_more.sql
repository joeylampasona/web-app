-- Four more blocks the Market Desk file has carried all along and the ingest
-- dropped: dealer gamma for the index and the sector funds (desk schema 1.3),
-- the squeeze read for the names its brief ranked (1.3), FINRA short interest
-- per flagged name (1.4), and the macro releases that fall inside a
-- five-session hold (1.4). One JSON object, stored whole like the others.
ALTER TABLE desk_runs ADD COLUMN extras TEXT NOT NULL DEFAULT 'null';
