from rrb.db import init_db
from rrb.generator import generate
from rrb.signals import compute_signals


def _first(conn, archetype):
    return conn.execute(
        "SELECT account_id FROM accounts WHERE archetype=? LIMIT 1",
        (archetype,)).fetchone()["account_id"]


def test_signal_fields(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    s = compute_signals(conn, _first(conn, "healthy_quiet"))
    assert s.days_to_renewal > 0
    assert 0 <= s.seat_utilization <= 1.5
    assert s.avg_tickets_per_month >= 0
    assert isinstance(s.has_qbr_docs, bool)


def test_declining_account_negative_trend(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    s = compute_signals(conn, _first(conn, "usage_declining"))
    assert s.usage_change_pct < -10


def test_support_burned_has_old_open_ticket(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=200)
    s = compute_signals(conn, _first(conn, "support_burned"))
    assert s.avg_tickets_per_month > 1.5
