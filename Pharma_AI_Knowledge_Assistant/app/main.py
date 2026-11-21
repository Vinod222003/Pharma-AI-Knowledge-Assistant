from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.models.document import Document, AuditLog
from app.api.routes import router

Path("data").mkdir(exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, version="1.0.0", description="Educational Advanced RAG capstone application")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8501"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
