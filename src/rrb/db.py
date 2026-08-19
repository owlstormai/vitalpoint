import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  specialty TEXT NOT NULL,
  city TEXT NOT NULL,
  state TEXT NOT NULL,
  seats INTEGER NOT NULL,
  arr INTEGER NOT NULL,
  contract_start TEXT NOT NULL,
  contract_end TEXT NOT NULL,
  auto_renew INTEGER NOT NULL CHECK (auto_renew IN (0, 1)),
  archetype TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_metrics (
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  month TEXT NOT NULL,
  logins INTEGER NOT NULL,
  active_users INTEGER NOT NULL,
  appointments INTEGER NOT NULL,
  PRIMARY KEY (account_id, month)
);
CREATE TABLE IF NOT EXISTS tickets (
  ticket_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  subject TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  doc_type TEXT NOT NULL,
  doc_date TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL
);
"""


def connect(path: str | Path, check_same_thread: bool = True,
            read_only: bool = False) -> sqlite3.Connection:
    """Open the database.

    read_only opens via a URI in ro mode, which is what serverless hosts need:
    their filesystem is read-only, and a normal open can fail when SQLite tries
    to create a journal beside the file.
    """
    if read_only:
        conn = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro",
                               uri=True, check_same_thread=check_same_thread)
    else:
        conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | Path) -> sqlite3.Connection:
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
