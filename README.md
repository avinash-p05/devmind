# DevMind

DevMind is an incident intelligence platform for grounded engineering answers across documentation, source code, logs, and incident reports.

## Local development

### Backend

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The API is available at `http://localhost:8000`. OpenAPI documentation is at `/docs`.

### Services

```powershell
docker compose up -d postgres redis
```

The current milestone runs a Postgres-backed document ingestion path with format-aware parsing for text, HTML, PDF, logs, incidents, and repository snapshots; deterministic local embeddings; pgvector hybrid search; a Redis-backed ingestion worker; a LangGraph-backed grounded assistant; structured incident analysis; and a versioned evaluation runner. The API exposes `/health`, `/documents`, `/ingestions`, `/ingestions/{job_id}`, `/search`, `/chat`, `/incidents/analyze`, `/evaluations/run`, and `/evaluations/{run_id}`. AWS deployment is added in a subsequent milestone.

To run the containerized stack:

```powershell
docker compose up -d --build --wait
```

Open `http://localhost:5173` for the UI or `http://localhost:8000/docs` for the API.

## Validation

```powershell
cd backend
uv run --extra dev pytest
uv run --extra dev ruff check .
```
