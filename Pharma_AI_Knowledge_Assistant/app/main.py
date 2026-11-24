from pathlib import Path
from fastapi import FastAPI
from app.core.config import settings
from app.core.database import Base, engine
from app.models.document import Document, AuditLog, User
from app.api.routes import router

Path("data").mkdir(exist_ok=True)
# Safe additive table creation only. Existing documents and audit records are not dropped.
Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name, version="2.0.0",
              description="Educational RAG prototype — not a validated GxP system")
app.include_router(router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
