from rrb.db import init_db
from rrb.generator import generate
from rrb.sentiment import score_satisfaction


def _docs(conn, archetype):
    acct = conn.execute(
        "SELECT account_id FROM accounts WHERE archetype=? LIMIT 1",
        (archetype,)).fetchone()["account_id"]
    return acct, conn.execute(
        "SELECT * FROM documents WHERE account_id=? AND doc_type IN "
        "('ticket','qbr')", (acct,)).fetchall()


def test_frustrated_archetype_scores_low(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=200)
    _, docs = _docs(conn, "support_burned")
    sat = score_satisfaction(docs)
    assert sat.label == "frustrated"
    assert sat.score < 40


def test_happy_archetype_scores_high(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=200)
    _, docs = _docs(conn, "healthy_quiet")
    sat = score_satisfaction(docs)
    assert sat.label == "happy"
    assert sat.score > 70


def test_quotes_are_verbatim_with_provenance(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=200)
    _, docs = _docs(conn, "support_burned")
    sat = score_satisfaction(docs)
    assert sat.quotes
    bodies = {d["doc_id"]: d["body"] for d in docs}
    for q in sat.quotes:
        assert q.text in bodies[q.doc_id]
        assert q.title and q.doc_date


def test_no_docs_returns_none_label(tmp_path):
    sat = score_satisfaction([])
    assert sat.label == "unknown" and sat.quotes == []
