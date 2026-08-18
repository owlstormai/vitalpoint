from rrb.db import init_db
from rrb.generator import generate


def _rows(conn, sql):
    return [tuple(r) for r in conn.execute(sql)]


def test_generates_requested_account_count(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=30)
    assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 30


def test_specialty_and_location_mix(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=60)
    specs = {r["specialty"] for r in conn.execute("SELECT specialty FROM accounts")}
    states = {r["state"] for r in conn.execute("SELECT state FROM accounts")}
    assert len(specs) >= 6
    assert len(states) >= 8


def test_deterministic_same_seed(tmp_path):
    c1 = init_db(tmp_path / "a.sqlite")
    c2 = init_db(tmp_path / "b.sqlite")
    generate(c1, seed=7, n_accounts=25)
    generate(c2, seed=7, n_accounts=25)
    assert _rows(c1, "SELECT * FROM accounts ORDER BY account_id") == _rows(
        c2, "SELECT * FROM accounts ORDER BY account_id")


def test_different_seed_differs(tmp_path):
    c1 = init_db(tmp_path / "a.sqlite")
    c2 = init_db(tmp_path / "b.sqlite")
    generate(c1, seed=7, n_accounts=25)
    generate(c2, seed=8, n_accounts=25)
    assert _rows(c1, "SELECT * FROM accounts ORDER BY account_id") != _rows(
        c2, "SELECT * FROM accounts ORDER BY account_id")
