CREATE TABLE IF NOT EXISTS signups (
  email TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  organisation TEXT,
  build TEXT,
  variant TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
  ip_hash TEXT NOT NULL,
  at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS attempts_ip_at ON attempts (ip_hash, at);
