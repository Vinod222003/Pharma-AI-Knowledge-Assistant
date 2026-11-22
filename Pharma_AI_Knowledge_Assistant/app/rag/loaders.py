
from pathlib import Path

import pandas as pd
from docx import Document as DocxDocument
from pypdf import PdfReader


SUPPORTED = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".xls"}


def _clean_text(text: str) -> str:
    """Normalize whitespace without losing meaningful content."""
    return "\n".join(
        line.strip()
        for line in text.splitlines()
        if line.strip()
    )


def load_file(path: str) -> list[dict]:
    """
    Extract text from supported document formats.

    Each result contains text and page information.
    Excel results also contain the worksheet name.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    ext = file_path.suffix.lower()

    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type: {ext}")

    pages = []

    try:
        # PDF extraction: retain the original PDF page number.
        if ext == ".pdf":
            reader = PdfReader(str(file_path))

            for page_number, page in enumerate(
                reader.pages,
                start=1
            ):
                text = _clean_text(page.extract_text() or "")

                pages.append({
                    "text": text,
                    "page": page_number,
                })

        # DOCX extraction: include paragraphs and tables.
        elif ext == ".docx":
            document = DocxDocument(str(file_path))

            content = []

            for paragraph in document.paragraphs:
                if paragraph.text.strip():
                    content.append(paragraph.text.strip())

            for table in document.tables:
                for row in table.rows:
                    cells = [
                        cell.text.strip().replace("\n", " ")
                        for cell in row.cells
                    ]

                    content.append(" | ".join(cells))

            pages.append({
                "text": _clean_text("\n".join(content)),
                "page": 1,
            })

        # TXT extraction.
        elif ext == ".txt":
            text = file_path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            )

            pages.append({
                "text": _clean_text(text),
                "page": 1,
            })

        # CSV extraction.
        elif ext == ".csv":
            dataframe = pd.read_csv(
                file_path,
                dtype=str,
                keep_default_na=False,
            )

            pages.append({
                "text": _clean_text(
                    dataframe.to_csv(index=False)
                ),
                "page": 1,
            })

        # Excel extraction: process every worksheet.
        else:
            workbook = pd.ExcelFile(file_path)

            for sheet_number, sheet_name in enumerate(
                workbook.sheet_names,
                start=1,
            ):
                dataframe = pd.read_excel(
                    workbook,
                    sheet_name=sheet_name,
                    dtype=str,
                    keep_default_na=False,
                )

                pages.append({
                    "text": _clean_text(
                        dataframe.to_csv(index=False)
                    ),
                    "page": sheet_number,
                    "sheet": sheet_name,
                })

    except Exception as error:
        raise ValueError(
            f"Could not process {file_path.name}: {error}"
        ) from error

    return pages


def chunk_text(
    text: str,
    size: int = 900,
    overlap: int = 150,
) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    size and overlap are measured in words, not characters.
    """

    if size <= 0:
        raise ValueError("Chunk size must be greater than zero.")

    if overlap < 0 or overlap >= size:
        raise ValueError(
            "Overlap must be non-negative and smaller than chunk size."
        )

    words = text.split()

    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + size, len(words))

        chunks.append(" ".join(words[start:end]))

        if end == len(words):
            break

        start = end - overlap

    return chunks
