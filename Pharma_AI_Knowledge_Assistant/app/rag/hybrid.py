"""Authorization-safe hybrid retrieval ranking primitives.

BM25 works over a *bounded set of SQL-authorized, active Chroma passages*;
RRF merges semantic similarity and lexical ranking without comparing scores.
"""
import math
from collections import Counter
from app.rag.retrieval import terms


def bm25_scores(query: str, passages: list[dict], k1: float = 1.5, b: float = .75) -> dict[str, float]:
    tokens = [terms(x['text']) for x in passages]
    query_terms = set(terms(query))
    n = len(tokens)
    if not n or not query_terms:
        return {}
    avgdl = max(sum(len(t) for t in tokens) / n, 1)
    df = Counter(word for doc in tokens for word in set(doc))
    scores = {}
    for passage, doc in zip(passages, tokens):
        freq = Counter(doc)
        score = 0.0
        for word in query_terms:
            if word not in freq:
                continue
            idf = math.log(1 + (n - df[word] + .5) / (df[word] + .5))
            score += idf * (freq[word] * (k1 + 1)) / (freq[word] + k1 * (1 - b + b * len(doc) / avgdl))
        scores[passage['id']] = score
    return scores


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    combined = {}
    for ranking in rankings:
        for rank, key in enumerate(dict.fromkeys(ranking), 1):
            combined[key] = combined.get(key, 0.0) + 1 / (k + rank)
    return combined


def rerank(query: str, passages: list[dict], model_name: str | None = None) -> list[dict]:
    """Optional local CrossEncoder. Failure degrades to hybrid rank, never bypasses RBAC."""
    if not passages or not model_name:
        return passages
    try:
        from sentence_transformers import CrossEncoder
        # Load only when explicitly enabled; CPU model can use substantial RAM.
        model = CrossEncoder(model_name, device='cpu')
        values = model.predict([(query, item['text']) for item in passages], show_progress_bar=False)
        return sorted(passages, key=lambda item: float(values[passages.index(item)]), reverse=True)
    except (ImportError, OSError, RuntimeError, ValueError):
        return passages
