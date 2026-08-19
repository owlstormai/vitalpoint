import pytest

from rrb.chunker import Chunk, chunk_documents
from rrb.db import init_db
from rrb.generator import generate
from rrb.index import HybridIndex


def _index(tmp_path, n=40):
    conn = init_db(tmp_path / "a.sqlite")
    labels = generate(conn, seed=42, n_accounts=n)
    return HybridIndex(chunk_documents(conn)), labels


def test_no_unscoped_retrieval_api(tmp_path):
    index, _ = _index(tmp_path)
    for name in ("retrieve", "search", "query"):
        assert not hasattr(index, name)


def test_scope_returns_only_own_account(tmp_path):
    index, labels = _index(tmp_path)
    acct = next(iter(labels))
    hits = index.for_account(acct).retrieve("support ticket", k=8)
    assert hits
    assert all(h.chunk.account_id == acct for h in hits)


def test_unknown_account_raises(tmp_path):
    index, _ = _index(tmp_path)
    with pytest.raises(KeyError):
        index.for_account("acct_9999")


def test_canary_never_leaks_across_scopes(tmp_path):
    index, labels = _index(tmp_path, n=60)
    ids = list(labels)
    for other in ids[:10]:
        canary = labels[other]["canary"]
        for acct in ids:
            if acct == other:
                continue
            hits = index.for_account(acct).retrieve(canary, k=5)
            assert all(canary not in h.chunk.text for h in hits)


def test_exact_phrase_found_in_own_scope(tmp_path):
    index, labels = _index(tmp_path)
    acct, lab = next(iter(labels.items()))
    hits = index.for_account(acct).retrieve(lab["canary"], k=5)
    assert any(lab["canary"] in h.chunk.text for h in hits)


def test_zero_overlap_query_returns_empty(tmp_path):
    index, labels = _index(tmp_path)
    acct = next(iter(labels))
    hits = index.for_account(acct).retrieve("zzqx wvvk pplm", k=5)
    assert hits == []


def test_tiny_vocab_account_survives_and_uses_bm25(tmp_path):
    chunk = Chunk(
        chunk_id="d#c0", doc_id="d", account_id="acct_x", doc_type="ticket",
        doc_date="2026-01-01", title="t", text="N/A")
    index = HybridIndex([chunk])
    scope = index.for_account("acct_x")
    hits = scope.retrieve("n", k=5)
    assert hits and hits[0].chunk == chunk
