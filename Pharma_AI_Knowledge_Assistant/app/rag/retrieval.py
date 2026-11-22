
import re
from pathlib import Path

import chromadb

from app.core.config import settings


_client = None
_RRF_K = 60
_MAX_LEXICAL_CANDIDATES = 5000
_STATUS_MIGRATION_COMPLETE = False
_UPDATE_BATCH_SIZE = 500


def collection():
    """Connect to ChromaDB and migrate legacy metadata."""
    global _client, _STATUS_MIGRATION_COMPLETE

    if _client is None:
        Path(settings.chroma_path).mkdir(
            parents=True,
            exist_ok=True,
        )

        _client = chromadb.PersistentClient(
            path=settings.chroma_path,
        )

    col = _client.get_or_create_collection(
        "pharma_knowledge"
    )

    if not _STATUS_MIGRATION_COMPLETE:
        result = col.get(include=["metadatas"])

        ids = result.get("ids") or []
        metadatas = result.get("metadatas") or []

        legacy_ids = []
        legacy_metadata = []

        for ident, metadata in zip(ids, metadatas):
            updated = dict(metadata or {})

            if "status" not in updated:
                updated["status"] = "active"
                legacy_ids.append(ident)
                legacy_metadata.append(updated)

        for start in range(
            0,
            len(legacy_ids),
            _UPDATE_BATCH_SIZE,
        ):
            end = start + _UPDATE_BATCH_SIZE

            col.update(
                ids=legacy_ids[start:end],
                metadatas=legacy_metadata[start:end],
            )

        _STATUS_MIGRATION_COMPLETE = True

    return col


def tokenize(text: str) -> list[str]:
    """Convert text into lowercase searchable terms."""
    return re.findall(r"\w+", text.lower())


def lexical_score(query: str, text: str) -> int:
    """Count query-term matches in a document."""
    terms = set(tokenize(query))
    words = tokenize(text)

    return sum(
        1 for word in words if word in terms
    )


def add_chunks(chunks: list[dict]):
    """Insert or update document chunks in ChromaDB."""
    if not chunks:
        return

    col = collection()

    for chunk in chunks:
        chunk["metadata"].setdefault(
            "status",
            "active",
        )

    col.upsert(
        ids=[x["id"] for x in chunks],
        documents=[x["text"] for x in chunks],
        metadatas=[x["metadata"] for x in chunks],
    )


def update_document_status(
    document_id: int,
    status: str,
) -> int:
    """Update the status of all chunks for one document."""

    if status not in {"active", "superseded"}:
        raise ValueError("Invalid document status.")

    col = collection()

    result = col.get(
        where={"document_id": document_id},
        include=["metadatas"],
    )

    ids = result.get("ids") or []
    metadatas = result.get("metadatas") or []

    if not ids:
        return 0

    updated_metadata = []

    for metadata in metadatas:
        updated = dict(metadata or {})
        updated["status"] = status
        updated_metadata.append(updated)

    for start in range(0, len(ids), _UPDATE_BATCH_SIZE):
        end = start + _UPDATE_BATCH_SIZE

        col.update(
            ids=ids[start:end],
            metadatas=updated_metadata[start:end],
        )

    return len(ids)


def _retrieval_filter(department: str | None):
    """Retrieve active documents for the selected department."""

    active_filter = {"status": "active"}

    if not department:
        return active_filter

    return {
        "$and": [
            active_filter,
            {
                "$or": [
                    {"department": department},
                    {"department": "general"},
                ]
            },
        ]
    }


def retrieve(
    query: str,
    n: int = 8,
    department: str | None = None,
) -> list[dict]:
    """
    Hybrid retrieval using semantic search,
    lexical search, and Reciprocal Rank Fusion.
    """

    if not query or not query.strip() or n <= 0:
        return []

    col = collection()
    total = col.count()

    if total == 0:
        return []

    where = _retrieval_filter(department)

    # Semantic retrieval
    vector_result = col.query(
        query_texts=[query],
        n_results=min(max(n * 5, 30), total),
        where=where,
    )

    vector_rows = []

    documents = vector_result.get("documents") or [[]]
    metadatas = vector_result.get("metadatas") or [[]]
    identifiers = vector_result.get("ids") or [[]]
    distances = vector_result.get("distances") or [[]]

    for doc, meta, ident, dist in zip(
        documents[0],
        metadatas[0],
        identifiers[0],
        distances[0],
    ):
        vector_rows.append({
            "id": ident,
            "text": doc or "",
            "metadata": meta or {},
            "distance": float(dist),
            "lexical": lexical_score(query, doc or ""),
        })

    # Lexical retrieval
    lexical_result = col.get(
        where=where,
        limit=min(total, _MAX_LEXICAL_CANDIDATES),
        include=["documents", "metadatas"],
    )

    lexical_rows = []

    for doc, meta, ident in zip(
        lexical_result.get("documents") or [],
        lexical_result.get("metadatas") or [],
        lexical_result.get("ids") or [],
    ):
        text = doc or ""
        score = lexical_score(query, text)

        if score > 0:
            lexical_rows.append({
                "id": ident,
                "text": text,
                "metadata": meta or {},
                "distance": 1.0,
                "lexical": score,
            })

    # Rank retrieval results
    vector_rows.sort(
        key=lambda item: item["distance"]
    )

    lexical_rows.sort(
        key=lambda item: item["lexical"],
        reverse=True,
    )

    # Reciprocal Rank Fusion
    fused = {}

    for rank, row in enumerate(vector_rows, start=1):
        ident = row["id"]

        if ident not in fused:
            fused[ident] = dict(row)
            fused[ident]["rrf_score"] = 0.0

        fused[ident]["rrf_score"] += (
            1.0 / (_RRF_K + rank)
        )

    for rank, row in enumerate(lexical_rows, start=1):
        ident = row["id"]

        if ident not in fused:
            fused[ident] = dict(row)
            fused[ident]["rrf_score"] = 0.0

        fused[ident]["rrf_score"] += (
            1.0 / (_RRF_K + rank)
        )

    rows = sorted(
        fused.values(),
        key=lambda item: item["rrf_score"],
        reverse=True,
    )

    return rows[:n]


def compress_context(
    query: str,
    passages: list[dict],
    max_chars: int = 7000,
) -> str:
    """Keep relevant sentences while limiting context size."""

    if not passages or max_chars <= 0:
        return ""

    terms = set(tokenize(query))
    output = []
    used = 0

    for passage in passages:
        text = passage.get("text", "")

        sentences = [
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])\s+",
                text,
            )
            if sentence.strip()
        ]

        ranked = sorted(
            enumerate(sentences),
            key=lambda item: (
                sum(
                    word in terms
                    for word in tokenize(item[1])
                ),
                -item[0],
            ),
            reverse=True,
        )

        excerpt = " ".join(
            sentence
            for _, sentence in ranked[:4]
        )[:1800]

        metadata = passage.get("metadata", {})

        filename = metadata.get(
            "filename",
            "Unknown",
        )

        page = metadata.get(
            "page",
            "N/A",
        )

        line = f"[{filename} | page {page}] {excerpt}"

        remaining = max_chars - used

        if remaining <= 0:
            break

        if len(line) > remaining:
            if not output:
                output.append(line[:remaining])
            break

        output.append(line)
        used += len(line)

    return "\n\n".join(output)
