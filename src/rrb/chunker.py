from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    account_id: str
    doc_type: str
    doc_date: str
    title: str
    text: str


def _split(body: str, max_words: int = 150) -> list[str]:
    parts, current = [], []
    for para in [p.strip() for p in body.split("\n\n") if p.strip()]:
        if sum(len(p.split()) for p in current) + len(para.split()) > max_words:
            if current:
                parts.append("\n\n".join(current))
            current = [para]
        else:
            current.append(para)
    if current:
        parts.append("\n\n".join(current))
    return parts or [body]


def chunk_documents(conn) -> list[Chunk]:
    chunks: list[Chunk] = []
    for row in conn.execute(
            "SELECT * FROM documents ORDER BY account_id, doc_id"):
        for k, text in enumerate(_split(row["body"])):
            chunks.append(Chunk(
                chunk_id=f"{row['doc_id']}#c{k}",
                doc_id=row["doc_id"],
                account_id=row["account_id"],
                doc_type=row["doc_type"],
                doc_date=row["doc_date"],
                title=row["title"],
                text=text,
            ))
    return chunks
