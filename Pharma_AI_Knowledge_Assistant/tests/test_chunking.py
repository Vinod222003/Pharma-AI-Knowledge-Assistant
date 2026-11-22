from app.rag.loaders import chunk_text

def test_empty():
    assert chunk_text("") == []

def test_chunk_overlap():
    assert chunk_text("one two three four five", size=3, overlap=1) == ["one two three", "three four five"]

def test_bad_overlap():
    import pytest
    with pytest.raises(ValueError):
        chunk_text("one", size=3, overlap=3)
