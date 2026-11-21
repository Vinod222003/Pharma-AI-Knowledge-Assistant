from app.rag.loaders import chunk_text

def test_chunk_text_empty():
    assert chunk_text("") == []

def test_chunk_text_returns_content():
    chunks = chunk_text("one two three four five", size=3, overlap=1)
    assert chunks
    assert "one" in chunks[0]
