import argparse
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document, AuditLog
from app.rag.loaders import load_file, chunk_text
from app.rag.retrieval import collection, add_chunks, update_document_status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        documents = db.scalars(
            select(Document).order_by(
                Document.filename,
                Document.version,
                Document.id
            )
        ).all()

        if not documents:
            print("No documents found.")
            return

        groups = defaultdict(list)
        for doc in documents:
            groups[doc.filename].append(doc)

        latest_by_filename = {}
        for filename, records in groups.items():
            latest = max(records, key=lambda d: (d.version, d.id))
            latest_by_filename[filename] = latest

        col = collection()

        print("\nDOCUMENT VERSION REPAIR PLAN")
        print("=" * 65)

        for filename, records in groups.items():
            latest = latest_by_filename[filename]
            for doc in records:
                target = "active" if doc.id == latest.id else "superseded"
                result = col.get(
                    where={"document_id": doc.id},
                    include=["metadatas"]
                )
                count = len(result.get("ids") or [])
                print(
                    f"ID={doc.id} | {filename} | Version={doc.version} "
                    f"| Current={doc.status} | Target={target} "
                    f"| Chunks={count}"
                )

        print("\nLatest documents missing from ChromaDB:")
        missing = []

        for filename, latest in latest_by_filename.items():
            result = col.get(
                where={"document_id": latest.id},
                include=["metadatas"]
            )
            if not result.get("ids"):
                missing.append(latest)
                print(f"- {filename} (ID={latest.id})")

        if not missing:
            print("- None")

        if not args.apply:
            print("\nPREVIEW ONLY: No database or ChromaDB records changed.")
            print("After reviewing this plan, run the script with --apply.")
            return

        print("\nApplying repair...")

        # Restore missing chunks for the latest versions.
        for doc in missing:
            source = Path(doc.storage_path)

            if not source.is_file():
                raise FileNotFoundError(
                    f"Uploaded file not found for document ID {doc.id}: {source}"
                )

            pages = load_file(str(source))
            chunks = []

            for page in pages:
                for part_no, part in enumerate(chunk_text(page["text"])):
                    chunks.append({
                        "id": f"{doc.id}_{page['page']}_{part_no}",
                        "text": part,
                        "metadata": {
                            "document_id": doc.id,
                            "filename": doc.filename,
                            "page": page["page"],
                            "department": doc.department,
                            "doc_type": doc.doc_type,
                            "version": doc.version,
                            "status": "active",
                        },
                    })

            if not chunks:
                raise RuntimeError(
                    f"No text chunks extracted from latest document: {doc.filename}"
                )

            add_chunks(chunks)
            print(f"Indexed {len(chunks)} chunks for {doc.filename}")

        # Update ChromaDB statuses for every version.
        for filename, records in groups.items():
            latest = latest_by_filename[filename]

            for doc in records:
                target = "active" if doc.id == latest.id else "superseded"
                update_document_status(doc.id, target)

        # Update PostgreSQL and record the repair in the audit log.
        for filename, records in groups.items():
            latest = latest_by_filename[filename]

            for doc in records:
                target = "active" if doc.id == latest.id else "superseded"

                if doc.status != target:
                    doc.status = target

            db.add(AuditLog(
                username="system",
                action="document_version_repair",
                detail=f"Repaired version history for {filename}; "
                       f"active version is {latest.version}."
            ))

        db.commit()

        print("\nRepair completed successfully.")
        print("PostgreSQL statuses and ChromaDB statuses have been updated.")


if __name__ == "__main__":
    main()
