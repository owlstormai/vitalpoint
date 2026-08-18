import yaml

from rrb.db import init_db
from rrb.generator import generate, write_labels


def _gen(tmp_path, n=80):
    conn = init_db(tmp_path / "a.sqlite")
    labels = generate(conn, seed=42, n_accounts=n)
    return conn, labels


def test_every_account_has_docs_and_canary(tmp_path):
    conn, labels = _gen(tmp_path)
    for acct_id, lab in labels.items():
        docs = conn.execute(
            "SELECT doc_type, body FROM documents WHERE account_id=?",
            (acct_id,)).fetchall()
        types = {d["doc_type"] for d in docs}
        assert "contract" in types
        assert lab["canary"] and any(lab["canary"] in d["body"] for d in docs)


def test_canaries_unique_and_absent_elsewhere(tmp_path):
    conn, labels = _gen(tmp_path)
    canaries = [l["canary"] for l in labels.values()]
    assert len(set(canaries)) == len(canaries)
    for acct_id, lab in labels.items():
        hit = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE account_id != ? AND body LIKE ?",
            (acct_id, f"%{lab['canary']}%")).fetchone()[0]
        assert hit == 0


def test_withheld_accounts_have_no_qbr(tmp_path):
    conn, labels = _gen(tmp_path, n=120)
    withheld = [a for a, l in labels.items() if "qbr_notes" in l["withheld"]]
    kept = [a for a, l in labels.items() if "qbr_notes" not in l["withheld"]]
    assert withheld and kept
    for a in withheld:
        n = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE account_id=? AND doc_type='qbr'",
            (a,)).fetchone()[0]
        assert n == 0
    n = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE account_id=? AND doc_type='qbr'",
        (kept[0],)).fetchone()[0]
    assert 2 <= n <= 4


def test_driver_evidence_recorded(tmp_path):
    conn, labels = _gen(tmp_path, n=120)
    flagged = [l for l in labels.values() if l["drivers"]]
    assert flagged
    for lab in flagged:
        for d in lab["drivers"]:
            assert d in lab["evidence"], f"no evidence doc for {d}"


def test_write_labels_roundtrip(tmp_path):
    conn, labels = _gen(tmp_path, n=10)
    p = tmp_path / "labels.yaml"
    write_labels(labels, p)
    assert yaml.safe_load(p.read_text()) == labels
