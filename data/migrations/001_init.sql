CREATE TABLE IF NOT EXISTS tickers (
    symbol      TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    type        TEXT NOT NULL DEFAULT 'CS',
    exchange    TEXT NOT NULL DEFAULT '',
    industry    TEXT NOT NULL DEFAULT '',
    list_date   TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bars (
    symbol  TEXT NOT NULL,
    date    TEXT NOT NULL,
    open    REAL NOT NULL,
    high    REAL NOT NULL,
    low     REAL NOT NULL,
    close   REAL NOT NULL,
    volume  REAL NOT NULL,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_bars_date ON bars(date);

CREATE TABLE IF NOT EXISTS fundamentals (
    symbol              TEXT PRIMARY KEY,
    shares_outstanding  REAL,
    shares_asof         TEXT,
    fetched_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS kv (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stage       TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'running',
    detail      TEXT NOT NULL DEFAULT ''
);
