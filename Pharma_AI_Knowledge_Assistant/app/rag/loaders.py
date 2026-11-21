from pathlib import Path
from pypdf import PdfReader
from docx import Document as DocxDocument
import pandas as pd

SUPPORTED = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".xls"}

def load_file(path: str) -> list[dict]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type: {ext}")
    pages = []
    if ext == ".pdf":
        for i, page in enumerate(PdfReader(str(p)).pages, start=1):
            pages.append({"text": page.extract_text() or "", "page": i})
    elif ext == ".docx":
        doc = DocxDocument(str(p))
        pages = [{"text": "\n".join(x.text for x in doc.paragraphs), "page": 1}]
    elif ext == ".txt":
        pages = [{"text": p.read_text(encoding="utf-8", errors="replace"), "page": 1}]
    elif ext == ".csv":
        pages = [{"text": pd.read_csv(p).to_csv(index=False), "page": 1}]
    else:
        book = pd.ExcelFile(p)
        for idx, sheet in enumerate(book.sheet_names, start=1):
            pages.append({"text": pd.read_excel(p, sheet_name=sheet).to_csv(index=False), "page": idx, "sheet": sheet})
    return pages

def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks
