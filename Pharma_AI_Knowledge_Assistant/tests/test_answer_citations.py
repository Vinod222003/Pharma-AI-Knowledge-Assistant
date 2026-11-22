"""Focused tests for citation retry, source-label validation, and abstention."""
from app.rag import answer as module

EVIDENCE = [{"text": "Recording a deviation includes an event identifier.",
             "metadata": {"filename": "demo_deviation_procedure.txt", "page": 1, "document_id": 6}}]


def _setup(monkeypatch):
    monkeypatch.setattr(module, "retrieve", lambda *a, **k: EVIDENCE)
    monkeypatch.setattr(module, "compress_context", lambda *a, **k: "[S1] Recording a deviation includes an event identifier.")


def test_retries_missing_citation(monkeypatch):
    _setup(monkeypatch)
    responses = iter(["Include an event identifier.", "Include an event identifier. [S1]"])
    monkeypatch.setattr(module, "_ask_ollama", lambda _: next(responses))
    result = module.answer_question("What should be recorded?", {"general"})
    assert not result["insufficient_evidence"]
    assert result["sources"][0]["filename"] == "demo_deviation_procedure.txt"
    assert "[S1]" in result["answer"]


def test_rejects_missing_citation_after_retry(monkeypatch):
    _setup(monkeypatch)
    monkeypatch.setattr(module, "_ask_ollama", lambda _: "Event identifier.")
    result = module.answer_question("What should be recorded?", {"general"})
    assert result["insufficient_evidence"]
    assert result["sources"] == []


def test_rejects_invalid_citation(monkeypatch):
    _setup(monkeypatch)
    monkeypatch.setattr(module, "_ask_ollama", lambda _: "Event identifier. [S99]")
    assert module.answer_question("What should be recorded?", {"general"})["insufficient_evidence"]


def test_accepts_correct_citation_first_try(monkeypatch):
    _setup(monkeypatch)
    count = []
    def fake(messages):
        count.append(messages)
        return "Include an event identifier. [S1]"
    monkeypatch.setattr(module, "_ask_ollama", fake)
    result = module.answer_question("What should be recorded?", {"general"})
    assert len(count) == 1
    assert not result["insufficient_evidence"]
