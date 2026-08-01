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

The current milestone runs a Postgres-backed document ingestion path with format-aware parsing for text, HTML, PDF, logs, incidents, and repository snapshots; bulk repository indexing with duplicate detection; deterministic local embeddings; pgvector hybrid search; a Redis-backed ingestion worker; a LangGraph-backed grounded assistant; structured incident analysis; and a versioned evaluation runner. The API exposes `/health`, `/documents`, `/repositories/index`, `/ingestions`, `/ingestions/{job_id}`, `/search`, `/chat`, `/conversations/{conversation_id}`, `/incidents/analyze`, `/evaluations/run`, and `/evaluations/{run_id}`.

To run the containerized stack:

```powershell
docker compose up -d --build --wait
```

Open `http://localhost:5173` for the UI or `http://localhost:8000/docs` for the API.

To generate a reproducible 1,000-document engineering fixture corpus and index it:

```powershell
uv run --directory backend python scripts/generate_demo_corpus.py data/demo-corpus --documents 1000
Invoke-RestMethod -Method Post -Uri http://localhost:8000/repositories/index `
  -ContentType "application/json" `
  -Body '{"path":"backend/data/demo-corpus","batch_size":100}'
```

## AWS deployment

The AWS target is defined in `infra/terraform` and provisions ECR, S3, RDS PostgreSQL,
ElastiCache Redis, ECS Fargate services, and an application load balancer. After building
and pushing the three images, copy `terraform.tfvars.example` to `terraform.tfvars`, set
the image URLs and database password, then run:

```powershell
cd infra/terraform
terraform init
terraform fmt -check
terraform validate
terraform apply
```

The GitHub Actions workflow runs backend tests/lint and the frontend production build on
pushes and pull requests.

## Validation

```powershell
cd backend
uv run --extra dev pytest
uv run --extra dev ruff check .
```
