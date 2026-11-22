# Enterprise AI Regulatory & Medical Knowledge Assistant

Educational pharmaceutical document-search capstone using FastAPI, PostgreSQL, ChromaDB, Ollama, and Streamlit. **Not a validated GxP system.** Do not use for patient care, batch release, regulatory submissions, or operational decisions.

## Existing installation: safe update

1. **Stop FastAPI and Streamlit. Back up the PostgreSQL database and `data/chroma` folder first.** Do not copy or delete database contents from another machine. If possible, test with a separate database first.
2. Keep your existing `.env`, `data/uploads`, and `data/chroma` files. Do **not** replace them with archive copies.
3. From your project root, activate `.venv` and run `python -m pip install -r requirements.txt`.
4. Edit local `.env` to set `JWT_SECRET` to a random value of at least 32 characters and verify DATABASE_URL, OLLAMA_URL, OLLAMA_MODEL. Do not share `.env`.
5. `python -m scripts.bootstrap_admin` creates an initial admin account. It does not overwrite existing users.
6. Start backend: `python -m uvicorn app.main:app --reload`. Start UI in a second terminal: `python -m streamlit run ui/Home.py`.
7. Open http://localhost:8501 and log in. API docs: http://127.0.0.1:8000/docs.

The new `users` table is created additively on startup by SQLAlchemy. **No existing document or audit table is dropped or changed.** Database changes should nevertheless be tested on a backed-up copy. The previous default API calls were anonymous; clients now require JWT login.

## What changed

- Explicit JWT authentication for protected APIs; admin user bootstrap; admin-managed user creation; role and department checks.
- Upload validation (size, extension, some magic bytes), duplicate hash check, extraction before SQL commit, and Chroma cleanup on failure.
- Version status changes: new active document replaces earlier active versions with the same filename and department; earlier vectors remain stored but are excluded from retrieval through SQL active-status checking.
- Query retrieval: allowed active document IDs, vector + bounded lexical candidates, word overlap gates, reciprocal-rank fusion, limited context, and cited-label verification.
- Configurable Ollama model/URL and a revised Streamlit dashboard.
- Unit tests and authenticated source-recall evaluator.

## Security and limitations

- Local prototype only. Not independently penetration-tested, GxP validated, or regulator-approved.
- Citation label verification does **not** prove each claim is entailed by the source. Human verification is mandatory.
- Retrieval thresholds are heuristics, not calibrated; a relevant short answer may be rejected, and unrelated overlapping material may still be returned. Tune with a labeled test collection.
- The lexical pass examines at most 2,000 chunks per query. This is for small capstone corpora, not enterprise scale.
- The project does not provide transactionally atomic updates across PostgreSQL, the file system, and ChromaDB. Recovery cleanup is best-effort and should be monitored.
- Simple metadata checks do not protect against every malformed file or malicious document. Only upload trusted documents in a local demo.
- Existing files already indexed by an earlier software version remain eligible if their SQL record is active. Review and supersede/restrict unrelated demo documents before using evaluations.
- JWTs are stored only in Streamlit session state and expire based on configured lifetime. Use HTTPS in any non-local deployment.
- No OCR for scanned PDFs; no production migrations, user-password reset workflow, or full audit of external admin actions.
- No Docker required for local mode. Ollama must be running and its configured model installed.

## Tests

Run `python -m pytest -q`. For integration evaluation, configure `EVAL_USERNAME` and `EVAL_PASSWORD` in your local shell (never share them), then run `python -m scripts.evaluate`. Source recall is only one metric; manually inspect citation grounding, refusal accuracy, and answer relevance.

## Main API routes

- `POST /api/auth/login` anonymous login
- `GET /api/auth/me` authenticated identity
- `POST /api/users`, `GET /api/users` admin only
- `POST /api/documents/upload` authenticated editor
- `GET /api/documents` document library (scoped)
- `POST /api/ask` grounded document question (scoped)
- `GET /api/audit` admin only
- `GET /health` basic service health

## Deployment

Local first. This educational build does not promise clinical safety, confidentiality, availability, or regulatory compliance. Review migration, access control, uploads, auditability, data retention, encryption, and validation before any real deployment.
