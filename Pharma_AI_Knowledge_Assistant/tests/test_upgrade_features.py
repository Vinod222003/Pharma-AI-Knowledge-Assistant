"""Pure logic and in-memory database tests; never require live Ollama/ChromaDB."""
from types import SimpleNamespace


def test_rrf_rankings():
    from app.rag.hybrid import reciprocal_rank_fusion
    scores = reciprocal_rank_fusion([["a", "b"], ["b", "a"]])
    assert scores["a"] == scores["b"]
    assert len(scores) == 2


def test_bm25_prefers_relevant_text():
    from app.rag.hybrid import bm25_scores
    items = [{"id": "a", "text": "batch release certificate analysis batch"},
             {"id": "b", "text": "library opening hours"}]
    scored = bm25_scores("batch release", items)
    assert scored["a"] > scored["b"]


def test_route_agent():
    from app.intelligence.operations import route_query
    assert route_query("How is an OOS batch released?") == "quality_agent"
    assert route_query("What does FDA regulation require?") == "regulatory_agent"
    assert route_query("Summarize the uploaded document") == "document_agent"


def test_gap_evidence_is_only_heuristic():
    from app.intelligence.operations import evidence_gap_analysis
    docs = [{"text": "Executed batch manufacturing record and certificate of analysis", "metadata": {"filename": "SOP.pdf", "page": 1}}]
    result = evidence_gap_analysis("batch manufacturing record; production calibration", docs)
    assert result["total_checks"] == 2
    assert result["with_potential_evidence"] == 1
    assert "not proof" in result["disclaimer"]


def test_pdf_report_contains_pdf_bytes():
    from app.intelligence.reporting import build_report
    data = build_report("Test", "What is QA?", "Supported fact [S1]", [{"label": "S1", "filename": "SOP.pdf", "page": 1}])
    assert data.startswith(b"%PDF")
    assert len(data) > 500


def test_evaluation_case():
    from app.intelligence.evaluation import evaluate_case
    result = evaluate_case({"answer": "Fact [S1]", "sources": [{"label": "S1", "filename": "SOP.pdf"}], "insufficient_evidence": False}, "SOP.pdf", False)
    assert result["citations_resolve"]
    assert result["expected_source_found"]
    assert result["evidence_flag_correct"]


def test_analytics_scoped_to_department():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.core.database import Base
    from app.models.document import Document
    from app.intelligence.operations import document_analytics
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Document(filename="qa.pdf", department="quality", status="active", storage_path="unused"),
                         Document(filename="restricted.pdf", department="regulatory", status="active", storage_path="unused")])
        session.commit()
        stats = document_analytics(session, {"quality", "general"})
        assert stats["active_documents"] == 1
        assert "regulatory" not in stats["by_department"]
