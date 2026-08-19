import json

from rrb.brief import build_brief
from rrb.chunker import chunk_documents
from rrb.cli import main as cli_main
from rrb.db import init_db
from rrb.export import brief_to_dict
from rrb.generator import generate
from rrb.index import HybridIndex


def _setup(tmp_path, n=60):
    conn = init_db(tmp_path / "a.sqlite")
    labels = generate(conn, seed=42, n_accounts=n)
    return conn, HybridIndex(chunk_documents(conn)), labels


def test_payload_is_json_serializable_and_complete(tmp_path):
    conn, index, labels = _setup(tmp_path)
    acct_id = next(iter(labels))
    acct = conn.execute("SELECT * FROM accounts WHERE account_id=?",
                        (acct_id,)).fetchone()
    payload = brief_to_dict(acct, build_brief(conn, index, acct_id))
    round_tripped = json.loads(json.dumps(payload))
    assert round_tripped["account"]["id"] == acct_id
    assert round_tripped["risk"]["level"] in {"low", "medium", "high"}
    assert isinstance(round_tripped["account"]["auto_renew"], bool)
    for key in ("satisfaction", "signals", "unknowns", "citations"):
        assert key in round_tripped


def test_every_driver_carries_its_evidence_or_an_explicit_null(tmp_path):
    """A CRM must be able to tell 'no evidence' from 'evidence omitted'."""
    conn, index, labels = _setup(tmp_path)
    seen_driver = False
    for acct_id in list(labels)[:20]:
        acct = conn.execute("SELECT * FROM accounts WHERE account_id=?",
                            (acct_id,)).fetchone()
        b = build_brief(conn, index, acct_id)
        payload = brief_to_dict(acct, b)
        for d in payload["risk"]["drivers"]:
            seen_driver = True
            assert "evidence" in d
            if d["evidence"] is not None:
                assert d["evidence"]["doc_id"] and d["evidence"]["excerpt"]
    assert seen_driver, "expected at least one risk driver across 20 accounts"


def test_cli_export_all_writes_json_array(tmp_path):
    db = tmp_path / "rrb.sqlite"
    out = tmp_path / "briefs.json"
    cli_main(["make-data", "--seed", "42", "--accounts", "10",
              "--db", str(db), "--labels", str(tmp_path / "l.yaml")])
    cli_main(["export", "--all", "--db", str(db), "--out", str(out)])
    data = json.loads(out.read_text())
    assert len(data) == 10
    assert {d["account"]["id"] for d in data} == {
        f"acct_{i:04d}" for i in range(10)}
