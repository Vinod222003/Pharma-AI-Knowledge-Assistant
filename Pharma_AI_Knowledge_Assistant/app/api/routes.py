import hashlib
import logging
import re
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.security import allowed_departments, create_token, current_user, require_editor, verify_password, hash_password, ROLES
from app.models.document import Document, AuditLog, User
from app.rag.loaders import SUPPORTED, chunk_text, load_file
from app.rag.retrieval import add_chunks, delete_document_chunks
from app.rag.answer import answer_question

router = APIRouter()
log = logging.getLogger(__name__)
DEPARTMENTS = {"general", "quality", "medical", "regulatory"}

class Login(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1)

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    department: str | None = None

class NewUser(BaseModel):
    username: str = Field(min_length=3, max_length=120, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: str = "viewer"
    department: str = "general"

@router.post("/auth/login")
def login(req: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == req.username, User.is_active == 1))
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    db.add(AuditLog(username=user.username, action="login", detail="Successful login"))
    db.commit()
    return {"access_token": create_token(user.username, user.role), "token_type": "bearer",
            "username": user.username, "role": user.role, "department": user.department}

@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "role": user.role, "department": user.department}

@router.post("/users")
def create_user(req: NewUser, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Admin permission required")
    if req.role not in ROLES or req.department not in DEPARTMENTS:
        raise HTTPException(400, "Invalid role or department")
    if req.role not in {"admin", "viewer", req.department}:
        raise HTTPException(400, "Department role must match department")
    if db.scalar(select(User).where(User.username == req.username)):
        raise HTTPException(409, "Username already exists")
    created = User(username=req.username, password_hash=hash_password(req.password), role=req.role, department=req.department)
    db.add(created)
    db.add(AuditLog(username=user.username, action="user_created", detail=req.username))
    db.commit()
    return {"username": created.username, "role": created.role, "department": created.department}

@router.get("/users")
def list_users(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Admin permission required")
    return [{"username": x.username, "role": x.role, "department": x.department, "active": bool(x.is_active)}
            for x in db.scalars(select(User).order_by(User.username)).all()]

@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), department: str = Query("general"), doc_type: str = Query("other"),
                          user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_editor(user)
    if department not in DEPARTMENTS or department not in allowed_departments(user):
        raise HTTPException(403, "Department not permitted")
    if not re.fullmatch(r"[A-Za-z0-9 _.-]{1,80}", doc_type):
        raise HTTPException(400, "Invalid document type")
    filename = Path((file.filename or "").replace("\\", "/")).name
    if not filename or len(filename) > 200 or filename in {".", ".."}:
        raise HTTPException(400, "Invalid filename")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, "Unsupported file type")
    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    await file.close()
    if not content:
        raise HTTPException(400, "File is empty")
    if len(content) > limit:
        raise HTTPException(413, "File exceeds upload limit")
    if suffix == ".pdf" and not content.lstrip().startswith(b"%PDF"):
        raise HTTPException(400, "Invalid PDF signature")
    if suffix in {".docx", ".xlsx"} and not content.startswith(b"PK"):
        raise HTTPException(400, "Invalid Office document")
    checksum = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Document).where(Document.filename == filename,
                      Document.department == department, Document.checksum == checksum, Document.status == "active"))
    if existing:
        raise HTTPException(409, f"Identical active document already exists (ID {existing.id})")
    dest = Path(settings.upload_dir) / f"{uuid.uuid4().hex}_{filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    new_id = None
    try:
        pages = load_file(str(dest))
        chunks = []
        for page in pages:
            for part, value in enumerate(chunk_text(page["text"])):
                chunks.append({"text": value, "page": int(page["page"]), "part": part})
        if not chunks:
            raise ValueError("No extractable text. Scanned PDFs require OCR and are not supported")
        previous = db.scalars(select(Document).where(Document.filename == filename,
                            Document.department == department).order_by(Document.version.desc())).all()
        version = max((x.version for x in previous), default=0) + 1
        record = Document(filename=filename, department=department, doc_type=doc_type, version=version,
                          storage_path=str(dest), checksum=checksum, status="indexing")
        db.add(record)
        db.flush()
        new_id = record.id
        payload = [{"id": f"{new_id}_{x['page']}_{x['part']}", "text": x["text"],
                    "metadata": {"document_id": new_id, "filename": filename, "page": x["page"],
                                 "department": department, "doc_type": doc_type, "version": version}} for x in chunks]
        add_chunks(payload)
        # Only activate new version once all chunks were successfully indexed.
        for old in previous:
            if old.status == "active":
                old.status = "superseded"
        record.status = "active"
        db.add(AuditLog(username=user.username, action="document_uploaded",
                        detail=f"id={new_id}; filename={filename}; version={version}; chunks={len(chunks)}"))
        db.commit()
        return {"document_id": new_id, "filename": filename, "version": version,
                "chunks_indexed": len(chunks), "message": "Upload and indexing completed"}
    except Exception as exc:
        db.rollback()
        if new_id is not None:
            try:
                delete_document_chunks(new_id)
            except Exception:
                log.exception("Chroma rollback failed for document %s", new_id)
        dest.unlink(missing_ok=True)
        log.exception("Document indexing failed")
        raise HTTPException(422, "Document extraction or indexing failed. Verify the file format and local services") from exc

@router.post("/ask")
def ask(req: AskRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty")
    permitted = allowed_departments(user)
    if req.department:
        if req.department not in permitted:
            raise HTTPException(403, "Department not permitted")
        permitted = {"general", req.department} if req.department != "general" else {"general"}
    result = answer_question(req.question.strip(), permitted)
    db.add(AuditLog(username=user.username, action="question_asked", detail=f"question_sha256={hashlib.sha256(req.question.encode()).hexdigest()}; sources={len(result['sources'])}"))
    db.commit()
    return result

@router.get("/documents")
def list_documents(user: User = Depends(current_user), db: Session = Depends(get_db)):
    docs = db.scalars(select(Document).where(Document.department.in_(allowed_departments(user))).order_by(Document.uploaded_at.desc())).all()
    return [{"id": x.id, "filename": x.filename, "department": x.department, "type": x.doc_type,
             "version": x.version, "status": x.status, "uploaded_at": x.uploaded_at.isoformat(),
             "checksum": x.checksum} for x in docs]

@router.get("/audit")
def audit(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Admin permission required")
    return [{"username": x.username, "action": x.action, "detail": x.detail, "created_at": x.created_at.isoformat()}
            for x in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)).all()]
