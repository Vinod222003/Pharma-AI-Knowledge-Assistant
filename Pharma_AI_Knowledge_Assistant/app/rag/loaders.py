from pathlib import Path
import pandas as pd
from pypdf import PdfReader
from docx import Document as DocxDocument
SUPPORTED = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".xls"}

def load_file(path: str) -> list[dict]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported extension {ext}")
    if ext == ".pdf":
        return [{"text": page.extract_text() or "", "page": i} for i, page in enumerate(PdfReader(str(p)).pages, 1)]
    if ext == ".docx":
        doc = DocxDocument(str(p))
        parts = [x.text for x in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return [{"text": "\n".join(parts), "page": 1}]
    if ext == ".txt":
        return [{"text": p.read_text(encoding="utf-8-sig", errors="replace"), "page": 1}]
    if ext == ".csv":
        return [{"text": pd.read_csv(p, dtype=str, keep_default_na=False).to_csv(index=False), "page": 1}]
    with pd.ExcelFile(p) as book:
        return [{"text": pd.read_excel(book, sheet_name=sheet, dtype=str).fillna("").to_csv(index=False),
                 "page": i, "sheet": sheet} for i, sheet in enumerate(book.sheet_names, 1)]

def chunk_text(text: str, size: int = 240, overlap: int = 40) -> list[str]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("size must be positive and overlap less than size")
    words = text.split()
    output = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        output.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return output
