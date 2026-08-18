import sqlite3

from rrb.db import connect, init_db


def test_init_db_creates_tables(tmp_path):
    conn = init_db(tmp_path / "t.sqlite")
    names = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"accounts", "usage_metrics", "tickets", "documents"} <= names


def test_connect_returns_row_factory(tmp_path):
    conn = init_db(tmp_path / "t.sqlite")
    conn.execute(
        "INSERT INTO accounts VALUES ('a1','Acme Dental','dental','Austin','TX',"
        "5,6000,'2025-09-01','2026-08-31',1,'healthy_quiet')"
    )
    row = conn.execute("SELECT * FROM accounts").fetchone()
    assert isinstance(row, sqlite3.Row)
    assert row["specialty"] == "dental"
