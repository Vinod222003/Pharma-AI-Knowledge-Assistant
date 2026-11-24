import math
import re
from collections import Counter
from pathlib import Path
import chromadb
from sqlalchemy import select
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document

_client = None
STOP = {"a","an","the","what","which","when","where","who","why","how","does","do","is","are","was","were","be","to","for","on","of","in","by","with","and","or","about","should","include","included","information","please","tell","me","this","that","from","recording"}

def terms(text):
    return [x for x in re.findall(r"[a-z0-9]+", text.lower()) if len(x) > 2 and x not in STOP]

def collection():
    global _client
    if _client is None:
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=settings.chroma_path)
    return _client.get_or_create_collection("pharma_knowledge")

def add_chunks(chunks):
    if not chunks:
        raise ValueError("Document had no indexable text")
    collection().upsert(ids=[x["id"] for x in chunks], documents=[x["text"] for x in chunks], metadatas=[x["metadata"] for x in chunks])

def delete_document_chunks(document_id: int):
    collection().delete(where={"document_id": document_id})

def eligible_docs(departments: set[str]):
    with SessionLocal() as db:
        docs = db.scalars(select(Document).where(Document.status == "active", Document.department.in_(departments))).all()
        return {d.id for d in docs}

def lexical_score(query, passage):
    q = set(terms(query))
    p = Counter(terms(passage))
    return sum(min(p[t], 3) for t in q)

def retrieve(query: str, n: int = 5, departments: set[str] | None = None):
    departments = departments or {"general"}
    active = eligible_docs(departments)
    if not active:
        return []
    col = collection()
    if col.count() == 0:
        return []
    # Limit to active, authorized SQL records before using a passage as evidence.
    where = {"document_id": {"$in": sorted(active)}}
    # Candidate sets: vectors and lexical matches from current permitted documents.
    # Bounded lexical scan keeps the educational app usable on an 8GB laptop.
    vector = col.query(query_texts=[query], n_results=min(50, col.count()), where=where, include=["documents","metadatas","distances"])
    candidates = {}
    for i, ident in enumerate(vector["ids"][0]):
        candidates[ident] = {"id": ident, "text": vector["documents"][0][i], "metadata": vector["metadatas"][0][i], "distance": vector["distances"][0][i]}
    offset = 0
    while offset < 2000:
        result = col.get(where=where, limit=200, offset=offset, include=["documents","metadatas"])
        if not result["ids"]:
            break
        for ident, doc, meta in zip(result["ids"], result["documents"], result["metadatas"]):
            candidates.setdefault(ident, {"id": ident, "text": doc, "metadata": meta, "distance": float("inf")})
        offset += len(result["ids"])
        if len(result["ids"]) < 200:
            break
    items = list(candidates.values())
    qterms = set(terms(query))
    if not qterms:
        return []
    for item in items:
        item["lexical"] = lexical_score(query, item["text"])
        item["coverage"] = len(qterms.intersection(terms(item["text"]))) / len(qterms)
    # Require domain-relevant word matches; vector closeness alone is insufficient.
    minimum = min(settings.rag_min_lexical_terms, len(qterms))
    filtered = [x for x in items if x["lexical"] >= minimum and x["coverage"] >= 0.34]
    if not filtered:
        return []
    from app.rag.hybrid import bm25_scores, reciprocal_rank_fusion, rerank
    bm25 = bm25_scores(query, filtered)
    vector_rank = [ident for ident in vector["ids"][0] if ident in {x['id'] for x in filtered}]
    keyword_rank = [x['id'] for x in sorted(filtered, key=lambda x: (bm25.get(x['id'], 0), x['coverage']), reverse=True)]
    fused = reciprocal_rank_fusion([vector_rank, keyword_rank])
    for item in filtered:
        item['bm25'] = round(bm25.get(item['id'], 0), 5)
        item['score'] = fused.get(item['id'], 0) + 0.025 * item['coverage']
    filtered.sort(key=lambda x: (x['score'], x['coverage']), reverse=True)
    # Rank only a small authorized shortlist; heavy reranker is opt-in.
    shortlisted = filtered[:max(n * 3, 10)]
    if settings.rag_reranker_enabled:
        shortlisted = rerank(query, shortlisted, settings.rag_reranker_model)
    return shortlisted[:n]

def compress_context(question, passages, max_chars=6500):
    query_terms = set(terms(question))
    lines, total = [], 0
    for index, passage in enumerate(passages, 1):
        sentences = re.split(r"(?<=[.!?])\s+|\n+", passage["text"])
        ranked = sorted(sentences, key=lambda s: len(query_terms.intersection(terms(s))), reverse=True)
        excerpt = " ".join(ranked[:5])[:1350]
        line = f"[S{index}] {passage['metadata'].get('filename')} (page {passage['metadata'].get('page')}): {excerpt}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n\n".join(lines)
