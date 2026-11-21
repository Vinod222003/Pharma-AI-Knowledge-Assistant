import hashlib, os, uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document, AuditLog
from app.rag.loaders import load_file, chunk_text, SUPPORTED
from app.rag.retrieval import add_chunks
from app.rag.answer import answer_question

router = APIRouter()

class AskRequest(BaseModel):
    question: str
    department: str | None = None

@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), department: str = Query("general"), doc_type: str = Query("other")):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, f"Supported formats: {', '.join(sorted(SUPPORTED))}")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File exceeds upload size limit")
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    checksum = hashlib.sha256(content).hexdigest()
    dest = Path(settings.upload_dir) / f"{uuid.uuid4().hex}_{safe_name}"
    dest.write_bytes(content)
    with SessionLocal() as db:
        prior = db.scalar(select(Document).where(Document.filename == safe_name).order_by(Document.version.desc()))
        version = (prior.version + 1) if prior else 1
        record = Document(filename=safe_name, department=department, doc_type=doc_type, version=version, storage_path=str(dest), checksum=checksum)
        db.add(record)
        db.add(AuditLog(username="system", action="document_uploaded", detail=f"{safe_name} version {version}"))
        db.commit()
        db.refresh(record)
        doc_id = record.id
    pages = load_file(str(dest))
    indexed = 0
    chunks = []
    for page in pages:
        for part_no, chunk in enumerate(chunk_text(page["text"])):
            chunks.append({"id": f"{doc_id}_{page['page']}_{part_no}", "text": chunk,
                "metadata": {"document_id": doc_id, "filename": safe_name, "page": page["page"],
                             "department": department, "doc_type": doc_type, "version": version}})
    add_chunks(chunks)
    indexed = len(chunks)
    return {"document_id": doc_id, "filename": safe_name, "version": version, "chunks_indexed": indexed, "message": "Upload and indexing completed"}

@router.post("/ask")
def ask(request: AskRequest):
    if not request.question.strip():
        raise HTTPException(400, "Question cannot be empty")
    return answer_question(request.question, request.department)

@router.get("/documents")
def list_documents():
    with SessionLocal() as db:
        docs = db.scalars(select(Document).order_by(Document.uploaded_at.desc())).all()
        return [{"id": d.id, "filename": d.filename, "department": d.department, "type": d.doc_type,
                 "version": d.version, "status": d.status, "uploaded_at": d.uploaded_at.isoformat()} for d in docs]
