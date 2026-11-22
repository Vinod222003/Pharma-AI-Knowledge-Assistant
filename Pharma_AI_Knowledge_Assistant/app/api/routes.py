
import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document, AuditLog
from app.rag.loaders import load_file, chunk_text, SUPPORTED
from app.rag.retrieval import add_chunks, update_document_status
from app.rag.answer import answer_question


router = APIRouter()
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str
    department: str | None = None


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    department: str = Query("general"),
    doc_type: str = Query("other"),
):
    """Upload, validate, version, and index a knowledge document."""

    original_name = (file.filename or "upload").replace("\\", "/")
    safe_name = Path(original_name).name

    if not safe_name or len(safe_name) > 255:
        raise HTTPException(400, "Invalid filename.")

    suffix = Path(safe_name).suffix.lower()

    if suffix not in SUPPORTED:
        raise HTTPException(
            400,
            f"Supported formats: {', '.join(sorted(SUPPORTED))}",
        )

    if not department.strip() or len(department) > 80:
        raise HTTPException(400, "Invalid department.")

    if not doc_type.strip() or len(doc_type) > 80:
        raise HTTPException(400, "Invalid document type.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    await file.close()

    if len(content) > max_bytes:
        raise HTTPException(413, "File exceeds upload size limit.")

    if not content:
        raise HTTPException(400, "Uploaded file is empty.")

    checksum = hashlib.sha256(content).hexdigest()

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / f"{uuid.uuid4().hex}_{safe_name}"

    # Check for an identical active document before creating a version.
    with SessionLocal() as db:
        duplicate = db.scalar(
            select(Document)
            .where(
                Document.filename == safe_name,
                Document.checksum == checksum,
                Document.status == "active",
            )
            .order_by(Document.version.desc())
        )

        if duplicate:
            return {
                "document_id": duplicate.id,
                "filename": duplicate.filename,
                "version": duplicate.version,
                "chunks_indexed": 0,
                "duplicate": True,
                "message": (
                    "Identical active document already exists. "
                    "No new version created."
                ),
            }

    # Save and extract the file before creating a database record.
    try:
        dest.write_bytes(content)
        pages = load_file(str(dest))

        chunks = []

        for page in pages:
            page_chunks = chunk_text(page["text"])

            for part_no, chunk in enumerate(page_chunks):
                chunks.append({
                    "page": page["page"],
                    "part_no": part_no,
                    "text": chunk,
                })

        if not chunks:
            raise HTTPException(
                422,
                "No readable text was found in the uploaded document.",
            )

    except HTTPException:
        dest.unlink(missing_ok=True)
        raise

    except Exception as exc:
        dest.unlink(missing_ok=True)
        logger.exception("Document extraction failed.")
        raise HTTPException(
            422,
            "Could not extract text from the uploaded document.",
        ) from exc

    document_id = None
    previous_active_ids = []
    version = 1

    try:
        # Create a processing record and determine the next version.
        with SessionLocal() as db:
            latest = db.scalar(
                select(Document)
                .where(Document.filename == safe_name)
                .order_by(Document.version.desc())
            )

            version = latest.version + 1 if latest else 1

            # Collect ALL previous active versions, not just one.
            previous_active_records = db.scalars(
                select(Document)
                .where(
                    Document.filename == safe_name,
                    Document.status == "active",
                )
                .order_by(Document.version.desc())
            ).all()

            previous_active_ids = [
                record.id for record in previous_active_records
            ]

            record = Document(
                filename=safe_name,
                department=department,
                doc_type=doc_type,
                version=version,
                status="processing",
                storage_path=str(dest),
                checksum=checksum,
            )

            db.add(record)
            db.flush()

            document_id = record.id

            db.add(
                AuditLog(
                    username="system",
                    action="document_upload_started",
                    detail=f"{safe_name} version {version}",
                )
            )

            db.commit()

        # Index the new version as processing, not yet searchable.
        chroma_chunks = []

        for item in chunks:
            chroma_chunks.append({
                "id": (
                    f"{document_id}_"
                    f"{item['page']}_"
                    f"{item['part_no']}"
                ),
                "text": item["text"],
                "metadata": {
                    "document_id": document_id,
                    "filename": safe_name,
                    "page": item["page"],
                    "department": department,
                    "doc_type": doc_type,
                    "version": version,
                    "status": "processing",
                },
            })

        add_chunks(chroma_chunks)

        # Activate the new version only after indexing succeeds.
        update_document_status(document_id, "active")

        # Supersede EVERY previous active version in ChromaDB.
        for old_id in previous_active_ids:
            update_document_status(old_id, "superseded")

        # Synchronize PostgreSQL and write audit history.
        with SessionLocal() as db:
            new_record = db.get(Document, document_id)

            if new_record is None:
                raise RuntimeError(
                    "New document record was not found."
                )

            new_record.status = "active"

            for old_id in previous_active_ids:
                old_record = db.get(Document, old_id)

                if old_record is not None:
                    old_record.status = "superseded"

                    db.add(
                        AuditLog(
                            username="system",
                            action="document_version_superseded",
                            detail=(
                                f"{safe_name} version "
                                f"{old_record.version} superseded "
                                f"by version {version}"
                            ),
                        )
                    )

            db.add(
                AuditLog(
                    username="system",
                    action="document_uploaded",
                    detail=(
                        f"{safe_name} version {version}; "
                        f"{len(chroma_chunks)} chunks indexed"
                    ),
                )
            )

            db.commit()

        return {
            "document_id": document_id,
            "filename": safe_name,
            "version": version,
            "chunks_indexed": len(chroma_chunks),
            "duplicate": False,
            "message": "Upload and indexing completed",
        }

    except Exception as exc:
        logger.exception("Document upload or indexing failed.")

        # Best-effort recovery: prevent a failed new version
        # from appearing in retrieval results.
        if document_id is not None:
            try:
                update_document_status(
                    document_id,
                    "superseded",
                )
            except Exception:
                logger.exception(
                    "Could not deactivate failed ChromaDB document."
                )

            # Restore ALL previous versions if their statuses changed.
            for old_id in previous_active_ids:
                try:
                    update_document_status(old_id, "active")
                except Exception:
                    logger.exception(
                        "Could not restore previous ChromaDB document "
                        "ID %s.",
                        old_id,
                    )

            try:
                with SessionLocal() as db:
                    failed_record = db.get(Document, document_id)

                    if failed_record is not None:
                        failed_record.status = "failed"

                    for old_id in previous_active_ids:
                        previous_record = db.get(Document, old_id)

                        if previous_record is not None:
                            previous_record.status = "active"

                    db.add(
                        AuditLog(
                            username="system",
                            action="document_upload_failed",
                            detail=f"{safe_name} version {version}",
                        )
                    )

                    db.commit()

            except Exception:
                logger.exception(
                    "Could not record failed upload status."
                )

        raise HTTPException(
            500,
            "Document upload or indexing failed. Check the application logs.",
        ) from exc


@router.post("/ask")
def ask(request: AskRequest):
    if not request.question.strip():
        raise HTTPException(400, "Question cannot be empty")

    return answer_question(
        request.question,
        request.department,
    )


@router.get("/documents")
def list_documents():
    with SessionLocal() as db:
        docs = db.scalars(
            select(Document).order_by(
                Document.uploaded_at.desc()
            )
        ).all()

        return [
            {
                "id": d.id,
                "filename": d.filename,
                "department": d.department,
                "type": d.doc_type,
                "version": d.version,
                "status": d.status,
                "uploaded_at": d.uploaded_at.isoformat(),
            }
            for d in docs
        ]
