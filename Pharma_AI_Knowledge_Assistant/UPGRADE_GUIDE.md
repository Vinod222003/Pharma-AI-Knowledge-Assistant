# Pharma AI Knowledge Assistant — Integrated v2 Upgrade

**Preserves the original FastAPI, JWT/RBAC, PostgreSQL, ChromaDB, Ollama and Streamlit design.**

## What was added

| Feature | Endpoint / location | Notes |
|---|---|---|
| BM25 + RRF hybrid ranking | `app/rag/hybrid.py`; existing `/api/ask` | Searches **only current, authorized SQL document IDs**; existing lexical coverage guard retained |
| CrossEncoder reranker | `rag_reranker_enabled=true` | Optional, CPU intensive, requires `sentence-transformers` and locally cached model |
| Routed specialized assistant | `POST /api/agents/ask` | Deterministic routing to QA, Regulatory, Document prompts; **not LangGraph autonomous agents** |
| SQL analytics | `GET /api/analytics` | Document counts scoped to RBAC, admin-only aggregated audit counts |
| SOP version comparison | `GET /api/documents/compare?first_id=&second_id=` | Compares permitted, stored **same-filename** versions; text changes, not regulatory compliance |
| Checklist evidence scan | `POST /api/compliance/gap-check` | Lexical evidence signals; **not automated compliance certification** |
| Downloadable reports | `POST /api/reports/answer.pdf` | In-memory, cited PDF generation; requires authorized login |
| Response metrics | `POST /api/evaluation/case` | Citation resolution checks, not comprehensive faithfulness evaluation |
| UI | Streamlit `ui/Home.py` | New SOP Intelligence and Evaluation & Reports tabs, analytics charts |

## Install on an existing Windows laptop

1. **Stop FastAPI/Streamlit**, back up your original folder and SQL/Chroma data. Do not overwrite `.env`, `data/chroma/`, `data/uploads/`, or PostgreSQL database.
2. Extract this ZIP alongside your existing project. Copy/merge the **source files** from this new folder into a *separate upgrade branch* or working copy, then review changes before replacing anything.
3. From the project directory, with the existing venv activated and `PYTHONHOME` configured as required on your laptop:

   ```powershell
   python -m pip install -r requirements.txt
   python -m pytest -q
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   In a second activated terminal: `python -m streamlit run ui/Home.py`.

4. To enable optional reranking on hardware with enough memory: `python -m pip install sentence-transformers`. Set `RAG_RERANKER_ENABLED=true` in your local `.env`. **Default is false** to fit the existing low-memory local workflow; the model download requires network access the first time.
5. PostgreSQL and Ollama must be running. The backend still expects the existing `.env` credentials and `qwen2.5:1.5b` model. Review the local model's speed and answer quality before enabling reranking.

## API examples (JWT authorization required)

`POST /api/agents/ask`

```json
{"question":"What does SOP-002 require for batch release?","department":"quality","agent":"auto"}
```

`POST /api/compliance/gap-check`

```json
{"checklist":"batch manufacturing record; certificate of analysis; environmental monitoring logs", "department":"quality"}
```

`GET /api/documents/compare?first_id=5&second_id=6` (only if both IDs refer to accessible versions of the same filename and department).

`POST /api/reports/answer.pdf` uses the same JSON fields as `/api/agents/ask` plus an optional report `title` and returns a PDF.

## Security and non-production limitations

- All new endpoints check JWT. Analytics/compare/checklist depend on existing `allowed_departments`; the existing upload/index status logic remains unchanged.
- Citation existence is **not factual entailment verification**. The original `answer.py` still uses simple missing-information phrase matching; it can make mistakes. Always verify pharmaceutical outputs against original approved controlled documents.
- Comparing versions or finding keyword overlaps cannot determine FDA/GMP approval. Synthetic SOP samples are educational only.
- No actual cloud deployment is included: Streamlit Community Cloud cannot automatically access private localhost PostgreSQL/Ollama/ChromaDB services. Hosting requires infrastructure, secrets management and additional testing.
- The archive intentionally includes **no** `.env`, uploaded PDFs, ChromaDB content, private credentials, pretrained models, or user data.

## Optional Docker demo deployment

A `docker-compose.upgrade.yml` overlay adds Streamlit and persistent uploads/Chroma volumes:

```bash
docker compose -f docker-compose.yml -f docker-compose.upgrade.yml up --build
```

This requires Docker, a valid `.env`, an Ollama service reachable from Docker containers, a downloaded local Ollama model, and a correctly initialized database. **Not tested in this environment** and not a hosted/public deployment. Streamlit Community Cloud alone cannot run this multi-service stack.
