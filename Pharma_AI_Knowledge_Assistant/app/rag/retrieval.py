import re
from pathlib import Path
import chromadb
from app.core.config import settings

_client = None
def collection():
    global _client
    if _client is None:
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=settings.chroma_path)
    return _client.get_or_create_collection("pharma_knowledge")

def lexical_score(query: str, text: str) -> int:
    terms = set(re.findall(r"\w+", query.lower()))
    words = re.findall(r"\w+", text.lower())
    return sum(1 for w in words if w in terms)

def add_chunks(chunks: list[dict]):
    if not chunks:
        return
    col = collection()
    col.upsert(
        ids=[x["id"] for x in chunks],
        documents=[x["text"] for x in chunks],
        metadatas=[x["metadata"] for x in chunks],
    )

def retrieve(query: str, n: int = 8, department: str | None = None) -> list[dict]:
    col = collection()
    count = col.count()
    if not count:
        return []
    result = col.query(query_texts=[query], n_results=min(n * 3, count))
    rows = []
    for doc, meta, ident, dist in zip(result["documents"][0], result["metadatas"][0], result["ids"][0], result["distances"][0]):
        if department and meta.get("department") not in (department, "general"):
            continue
        rows.append({"id": ident, "text": doc, "metadata": meta, "distance": dist,
                     "lexical": lexical_score(query, doc)})
    # Hybrid baseline: vector rank plus lexical relevance; transparent and replaceable.
    rows.sort(key=lambda x: (x["lexical"], -x["distance"]), reverse=True)
    return rows[:n]

def compress_context(query: str, passages: list[dict], max_chars: int = 7000) -> str:
    terms = set(re.findall(r"\w+", query.lower()))
    out, used = [], 0
    for p in passages:
        sentences = re.split(r"(?<=[.!?])\s+", p["text"])
        ranked = sorted(sentences, key=lambda s: sum(w in s.lower() for w in terms), reverse=True)
        excerpt = " ".join(ranked[:4])[:1800]
        line = f"[{p['metadata'].get('filename')} | page {p['metadata'].get('page')}] {excerpt}"
        if used + len(line) > max_chars:
            break
        out.append(line); used += len(line)
    return "\n\n".join(out)
