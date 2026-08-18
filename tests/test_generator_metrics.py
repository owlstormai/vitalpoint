from rrb.db import init_db
from rrb.generator import N_MONTHS, generate


def test_usage_rows_per_account(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=10)
    n = conn.execute("SELECT COUNT(*) FROM usage_metrics").fetchone()[0]
    assert n == 10 * N_MONTHS


def test_declining_archetype_usage_falls(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    row = conn.execute(
        "SELECT account_id FROM accounts WHERE archetype='usage_declining' LIMIT 1"
    ).fetchone()
    assert row, "seed 42 with 120 accounts should include usage_declining"
    months = [r["logins"] for r in conn.execute(
        "SELECT logins FROM usage_metrics WHERE account_id=? ORDER BY month",
        (row["account_id"],))]
    assert sum(months[-3:]) < sum(months[:3]) * 0.8


def test_ticket_volume_tracks_archetype(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    burned = conn.execute(
        "SELECT COUNT(*) n FROM tickets t JOIN accounts a USING(account_id) "
        "WHERE a.archetype='support_burned'").fetchone()["n"]
    quiet = conn.execute(
        "SELECT COUNT(*) n FROM tickets t JOIN accounts a USING(account_id) "
        "WHERE a.archetype='healthy_quiet'").fetchone()["n"]
    n_burned = conn.execute(
        "SELECT COUNT(*) n FROM accounts WHERE archetype='support_burned'"
    ).fetchone()["n"]
    n_quiet = conn.execute(
        "SELECT COUNT(*) n FROM accounts WHERE archetype='healthy_quiet'"
    ).fetchone()["n"]
    assert n_burned and n_quiet
    assert burned / n_burned > 3 * (quiet / max(n_quiet, 1))


def test_some_tickets_left_open(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    open_n = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
    assert open_n > 0
