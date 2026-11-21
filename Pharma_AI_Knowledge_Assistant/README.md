# Enterprise AI Regulatory & Medical Knowledge Assistant
**Capstone project starter — Advanced RAG for pharmaceutical operations**

This repository provides a runnable end-to-end application scaffold with:
- FastAPI backend and Streamlit interface
- PostgreSQL document metadata and audit records
- ChromaDB vector retrieval
- OpenAI-compatible LLM and embeddings integration
- PDF, DOCX, TXT, CSV and XLSX ingestion
- Query expansion, hybrid retrieval, metadata filtering, reranking, context compression and conversation history hooks
- JWT authentication with role-based access scaffolding
- Document versioning, source citations, evaluation script, Docker Compose and synthetic demo files

> **Safety and scope:** This is an educational capstone, not a validated GxP system or medical/regulatory decision-maker. Demo content is synthetic and must not be treated as pharmaceutical guidance. Never upload confidential, personal, patient, or regulated company documents to an unapproved service. Validate all outputs with qualified personnel and approved source documents.

## 1. Requirements
- Python 3.14 (target)
- PostgreSQL 18 (or compatible PostgreSQL)
- OpenAI API key (or compatible endpoint)
- Docker Desktop is optional for local development

Python 3.14 support varies by third-party package and platform. If installation reports that a dependency has no compatible wheel, do not force-install it; check the package's current Python support and use the documented alternative. The app itself targets Python 3.14.

## 2. Quick start — Windows PowerShell
Run commands from the project root:

```powershell
# Activate the existing virtual environment
.\.venv\Scripts\Activate.ps1

# Update packaging tools
python -m pip install --upgrade pip setuptools wheel

# Install application dependencies
python -m pip install -r requirements.txt

# Create local environment file
Copy-Item .env.example .env

# Edit .env and enter your API key and PostgreSQL connection details.
# Do not share .env or commit it to Git.

# Create the PostgreSQL database (run in psql as a database administrator)
# CREATE DATABASE pharma_rag;

# Start the API
python -m uvicorn app.main:app --reload

# In a second terminal, activate .venv and start the UI
streamlit run ui/Home.py
```

Open:
- API docs: http://127.0.0.1:8000/docs
- Streamlit UI: http://localhost:8501
- Health check: http://127.0.0.1:8000/health

## 3. PostgreSQL setup
The default database URL is:
`postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/pharma_rag`

Change username/password in `.env`. Create the database first:
```sql
CREATE DATABASE pharma_rag;
```
Tables are created automatically on API startup for this development scaffold.

## 4. Ingest and query
1. Start the API and Streamlit UI using the commands above.
2. Upload a synthetic or approved document.
3. Ask a question that can be answered from the uploaded material.
4. Review the returned source filenames, page numbers and excerpts.
5. If evidence is insufficient, the assistant should say so rather than invent an answer.

## 5. Roles
The starter includes JWT/password utility functions and defines the intended `admin`, `regulatory`, `medical`, `quality`, and `viewer` role set. Full user management, login endpoints, and route-level authorization are not yet wired into the UI/API; treat authentication as a capstone implementation milestone, not a completed security feature. Before any real deployment, replace the default secret, enforce HTTPS, harden password policy, add account lifecycle controls, and conduct a security review.

## 6. Advanced RAG modules
- Query expansion: generate alternative searches from the original question.
- Hybrid retrieval: combine vector similarity and lexical keyword matching.
- Metadata filtering: filter by document type, version and department.
- Reranking: rerank retrieved passages using lexical relevance as a baseline.
- Context compression: trim passages to the most relevant sentences.
- Conversation memory: retain recent turns in the UI session.
- Versioning: each uploaded file is assigned a version number.
- Citations: responses include source filename, page and excerpt.

These are implemented as transparent baseline methods suitable for learning and evaluation. For a production-grade system, benchmark stronger cross-encoder rerankers, hybrid fusion strategies, access-control filtering at retrieval time, and a formally validated evaluation dataset.

## 7. Evaluation
Run:
```powershell
python -m pip install -r requirements.txt
python scripts/evaluate.py
```
The included evaluation file is a small synthetic smoke-test set, not evidence of regulatory validation. Expand it with expert-reviewed questions, expected evidence, groundedness, citation precision/recall, retrieval recall@k, latency and failure analysis.

## 8. Git / GitHub
```powershell
git init
git add .
git commit -m "Initial capstone project scaffold"
```
Create an empty GitHub repository, then follow GitHub's displayed instructions to add its remote and push. Never commit `.env`, API keys, real pharmaceutical documents, local databases, `.venv`, or Chroma storage.

## 9. Troubleshooting
- **Python warning about platform independent libraries:** this can indicate a Python installation/venv configuration issue. If Python and pip work, the app can still be generated; investigate before installing packages if imports or installs fail.
- **Dependency has no Python 3.14 wheel:** check the package's official release notes. Do not randomly downgrade packages. This scaffold keeps dependencies in one requirements file so they can be adjusted.
- **PostgreSQL connection refused:** confirm the PostgreSQL service is running, the database exists, and `.env` credentials are correct.
- **Chroma storage:** local vector data is stored under `data/chroma/` and is excluded from Git.
- **Docker engine unavailable:** use the local Python steps above; Docker is optional.

## Project layout
```text
app/
  api/             FastAPI routes
  core/            settings, auth and database
  rag/             loaders, chunking, retrieval, generation
  models/           SQLAlchemy models
ui/                 Streamlit user interface
data/demo_docs/     Synthetic demo source
scripts/            Evaluation helper
tests/              Smoke tests
```
