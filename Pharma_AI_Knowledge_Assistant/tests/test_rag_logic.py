from app.rag.retrieval import lexical_score, terms
from app.core.security import hash_password, verify_password

def test_lexical_domain_matches():
    assert lexical_score("recording a deviation", "deviation event date and reporter") > lexical_score("recording a deviation", "training institute phone and fees")

def test_stopwords_removed():
    assert "what" not in terms("What is a deviation?")

def test_password_hash():
    stored = hash_password("sufficiently-long-secret")
    assert verify_password("sufficiently-long-secret", stored)
    assert not verify_password("wrong", stored)
