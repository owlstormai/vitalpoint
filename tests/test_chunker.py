from rrb.chunker import chunk_documents
from rrb.db import init_db
from rrb.generator import generate


def test_chunks_carry_metadata(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=20)
    chunks = chunk_documents(conn)
    assert chunks
    for c in chunks:
        assert c.account_id.startswith("acct_")
        assert c.doc_type in {"contract", "ticket", "qbr"}
        assert c.doc_date and c.title and c.text.strip()
        assert len(c.text.split()) <= 160


def test_chunk_ids_unique(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=20)
    chunks = chunk_documents(conn)
    ids = [c.chunk_id for c in chunks]
    assert len(set(ids)) == len(ids)
