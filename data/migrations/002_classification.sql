CREATE TABLE IF NOT EXISTS universe (
    symbol       TEXT PRIMARY KEY,
    as_of        TEXT NOT NULL,
    price        REAL NOT NULL,
    market_cap   REAL,
    adv20        REAL,
    industry     TEXT NOT NULL DEFAULT '',
    passed       INTEGER NOT NULL DEFAULT 0,
    rejected_at  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS theme_members (
    symbol      TEXT NOT NULL,
    theme_slug  TEXT NOT NULL,
    PRIMARY KEY (symbol, theme_slug)
);
CREATE INDEX IF NOT EXISTS idx_theme_members_theme ON theme_members(theme_slug);
