import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from rrb.chunker import Chunk

RRF_K = 60
_TOKEN = re.compile(r"[a-z0-9]+")
# scikit-learn's default token pattern, matched here so the dense leg behaves
# exactly as it did when this used TfidfVectorizer
_WORD = re.compile(r"\w\w+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class _TfIdf:
    """TF-IDF vectors with cosine similarity, in about twenty lines.

    This reproduces scikit-learn's TfidfVectorizer defaults — smooth IDF,
    raw term counts, L2-normalized vectors, two-or-more-character word tokens
    — because pulling numpy, scipy and scikit-learn (~140 MB) into the
    dependency tree to vectorize at most eight short documents per account is
    not a trade worth making. Cosine similarity on L2-normalized vectors is
    just their dot product, so the whole dense leg is a sparse dict product.
    """

    def __init__(self, docs: list[str]):
        counts = [Counter(_WORD.findall(d.lower())) for d in docs]
        df: Counter = Counter()
        for c in counts:
            df.update(c)
        if not df:
            # mirrors sklearn's "empty vocabulary" error so callers can fall
            # back to BM25-only scoring for a chunk set with no usable tokens
            raise ValueError("empty vocabulary")
        n = len(docs)
        self._idf = {t: math.log((1 + n) / (1 + d)) + 1.0
                     for t, d in df.items()}
        self._vectors = [self._vectorize(c) for c in counts]

    def _vectorize(self, counts: Counter) -> dict[str, float]:
        vec = {t: c * self._idf[t] for t, c in counts.items() if t in self._idf}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        return {t: v / norm for t, v in vec.items()} if norm else {}

    def similarities(self, query: str) -> list[float]:
        q = self._vectorize(Counter(_WORD.findall(query.lower())))
        return [sum(w * doc.get(t, 0.0) for t, w in q.items())
                for doc in self._vectors]


@dataclass(frozen=True)
class Retrieved:
    chunk: Chunk
    score: float
    matched_terms: int


class _BM25:
    def __init__(self, docs: list[list[str]], k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = docs
        self.doc_len = [len(d) for d in docs]
        self.avg_len = sum(self.doc_len) / max(len(docs), 1)
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5))
                    for t, c in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for i in range(len(self.docs)):
            s = 0.0
            for t in query:
                if t not in self.tf[i]:
                    continue
                f = self.tf[i][t]
                denom = f + self.k1 * (
                    1 - self.b + self.b * self.doc_len[i] / self.avg_len)
                s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            out.append(s)
        return out


class AccountScope:
    """Retrieval over exactly one account's chunks. Built from scoped chunks
    only — other tenants' text is not present in any scoring structure."""

    def __init__(self, account_id: str, chunks: list[Chunk]):
        self.account_id = account_id
        self._chunks = chunks
        # Rank over title + body: document titles ("Overcharged on last
        # invoice") are the most discriminative signal in this corpus, and
        # scoring them keeps ranking consistent with matched_terms below.
        searchable = [c.title + " " + c.text for c in chunks]
        self._chunk_tokens = [set(_tokens(s)) for s in searchable]
        self._bm25 = _BM25([_tokens(s) for s in searchable])
        try:
            self._tfidf = _TfIdf(searchable)
        except ValueError:
            # a chunk set with an empty vocabulary (e.g. a single chunk like
            # "N/A" with no usable tokens) degrades to BM25-only scoring for
            # this scope rather than crashing
            self._tfidf = None

    def retrieve(self, query: str, k: int = 5) -> list[Retrieved]:
        if not self._chunks:
            return []
        q_tokens = _tokens(query)
        bm = self._bm25.scores(q_tokens)
        rankings = [bm]
        if self._tfidf is not None:
            rankings.append(self._tfidf.similarities(query))
        rrf: defaultdict[int, float] = defaultdict(float)
        for ranking in rankings:
            order = sorted(range(len(self._chunks)),
                           key=lambda i: ranking[i], reverse=True)
            for rank, i in enumerate(order):
                if ranking[i] > 0:
                    rrf[i] += 1.0 / (RRF_K + rank + 1)
        if not rrf:
            # No lexical or semantic overlap at all. Cite-or-abstain: return
            # nothing rather than handing back unrelated chunks that
            # downstream code might mistake for evidence.
            return []
        top = sorted(rrf.items(), key=lambda kv: kv[1], reverse=True)[:k]
        q_set = set(q_tokens)
        return [Retrieved(self._chunks[i], s,
                          len(q_set & self._chunk_tokens[i]))
                for i, s in top]


class HybridIndex:
    """Holds all chunks grouped by account. Deliberately exposes no unscoped
    search — the only way to retrieve is through for_account()."""

    def __init__(self, chunks: list[Chunk]):
        self._by_account: dict[str, list[Chunk]] = defaultdict(list)
        for c in chunks:
            self._by_account[c.account_id].append(c)
        self._scopes: dict[str, AccountScope] = {}

    @property
    def account_ids(self) -> list[str]:
        return sorted(self._by_account)

    def for_account(self, account_id: str) -> AccountScope:
        if account_id not in self._by_account:
            raise KeyError(f"unknown account: {account_id}")
        if account_id not in self._scopes:
            self._scopes[account_id] = AccountScope(
                account_id, list(self._by_account[account_id]))
        return self._scopes[account_id]
