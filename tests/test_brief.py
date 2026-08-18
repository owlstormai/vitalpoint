from rrb.brief import build_brief
from rrb.chunker import chunk_documents
from rrb.db import init_db
from rrb.generator import generate
from rrb.index import HybridIndex


def _setup(tmp_path, n=120):
    conn = init_db(tmp_path / "a.sqlite")
    labels = generate(conn, seed=42, n_accounts=n)
    return conn, HybridIndex(chunk_documents(conn)), labels


def test_brief_has_all_sections(tmp_path):
    conn, index, labels = _setup(tmp_path)
    b = build_brief(conn, index, next(iter(labels)))
    for heading in ("# Renewal Risk Brief", "## Risk", "## Customer Sentiment",
                    "## Recent History", "## Recommended Actions",
                    "## What We Don't Know"):
        assert heading in b.markdown


def test_citations_are_faithful(tmp_path):
    conn, index, labels = _setup(tmp_path)
    for acct in list(labels)[:15]:
        b = build_brief(conn, index, acct)
        for cit in b.citations:
            body = conn.execute(
                "SELECT body FROM documents WHERE doc_id=?",
                (cit.doc_id,)).fetchone()["body"]
            assert cit.excerpt in body


def test_citations_scoped_to_account(tmp_path):
    conn, index, labels = _setup(tmp_path)
    for acct in list(labels)[:15]:
        b = build_brief(conn, index, acct)
        for cit in b.citations:
            owner = conn.execute(
                "SELECT account_id FROM documents WHERE doc_id=?",
                (cit.doc_id,)).fetchone()["account_id"]
            assert owner == acct


def test_withheld_qbr_appears_in_unknowns(tmp_path):
    conn, index, labels = _setup(tmp_path, n=200)
    withheld = [a for a, l in labels.items() if "qbr_notes" in l["withheld"]]
    assert withheld
    b = build_brief(conn, index, withheld[0])
    assert "qbr_notes" in b.unknowns
    normal = [a for a, l in labels.items() if not l["withheld"]][0]
    b2 = build_brief(conn, index, normal)
    assert "qbr_notes" not in b2.unknowns


def test_healthy_account_evidence_never_misattributes_unrelated_quote(tmp_path):
    # Regression: a healthy account's glowing QBR line was previously being
    # cited as "Evidence:" for an unrelated risk driver (e.g.
    # unresolved_tickets) because the old code took the top-1 retrieval hit
    # unconditionally. The relevance floor (matched_terms >= 2) should stop
    # that — this praise line should never show up after "Evidence:".
    conn, index, labels = _setup(tmp_path, n=200)
    healthy = [a for a in labels if conn.execute(
        "SELECT archetype FROM accounts WHERE account_id=?",
        (a,)).fetchone()["archetype"] == "healthy_quiet"]
    assert healthy
    for acct in healthy:
        b = build_brief(conn, index, acct)
        for line in b.markdown.splitlines():
            if "Evidence:" in line:
                assert "praised the reminder feature" not in line


def test_billing_dispute_names_the_problem(tmp_path):
    conn, index, labels = _setup(tmp_path, n=200)
    acct = next(a for a in labels if conn.execute(
        "SELECT archetype FROM accounts WHERE account_id=?",
        (a,)).fetchone()["archetype"] == "billing_dispute")
    b = build_brief(conn, index, acct)
    assert "billing_dispute" in b.markdown
    actions_section = b.markdown.split("## Recommended Actions", 1)[1]
    actions_section = actions_section.split("## What We Don't Know", 1)[0]
    assert "disputed invoice" in actions_section
