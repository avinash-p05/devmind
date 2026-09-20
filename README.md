# DevMind

DevMind is an incident-intelligence platform for grounded engineering answers
across documentation, source code, logs, deployment records, and incident reports.
It combines format-aware ingestion, PostgreSQL/pgvector retrieval, PostgreSQL
full-text search, rank-aware reranking, Redis-backed jobs, and LangGraph workflow
orchestration behind a FastAPI API and React UI.

> **Implementation status:** This repository contains a working local POC with
> configurable local or OpenAI-compatible embedding and LLM providers. The
> default local mode is deterministic for repeatable tests; the Docker Compose
> stack can use the provider settings from the ignored root `.env` file. AWS
> infrastructure is defined but has not been independently verified as a live
> production deployment.

## System architecture

```mermaid
flowchart TD
    UI[React + TypeScript UI] --> API[FastAPI API]
    API --> REQUEST[Request ID + observability middleware]
    REQUEST --> GRAPH[LangGraph agent workflow]
    REQUEST --> PERSIST[(Conversation + telemetry persistence)]
    API --> INGEST_API[Document/repository/queue endpoints]
    INGEST_API --> REDIS[(Redis queue + job state)]
    REDIS --> WORKER[Async ingestion worker]
    WORKER --> PARSE[Format-aware parser]
    PARSE --> CHUNK[Normalize + chunk + metadata]
    CHUNK --> EMBED[Embedding provider]
    EMBED --> DB[(PostgreSQL + pgvector)]
    GRAPH --> ANALYZE[Query analyzer/router]
    ANALYZE --> CODE[Code-search tool]
    ANALYZE --> RETRIEVE[Hybrid retrieval tool]
    CODE --> RETRIEVE
    RETRIEVE --> VECTOR[pgvector vector search]
    RETRIEVE --> KEYWORD[PostgreSQL full-text search]
    VECTOR --> FUSE[Candidate merge + RRF reranking]
    KEYWORD --> FUSE
    FUSE --> GENERATE[Grounded LLM/local generator]
    GENERATE --> VALIDATE[Citation ID validator]
    VALIDATE -->|invalid or missing citations| CORRECT[One bounded correction retry]
    CORRECT --> VALIDATE
    VALIDATE --> RESPONSE[Answer + evidence + metrics]
    RESPONSE --> API
    GRAPH --> DB
```

### Runtime components

| Component | Responsibility |
| --- | --- |
| React/Vite frontend | Ingest sources, index repositories, search evidence, ask questions, analyze incidents, and run evaluations |
| FastAPI | HTTP API, request validation, request IDs, persistence coordination, and OpenAPI documentation |
| LangGraph | Query routing, retrieval tool selection, bounded evidence retry, answer generation, citation validation, and incident analysis |
| Embedding service | Deterministic local embeddings for tests or OpenAI-compatible remote embeddings for real indexing |
| LLM service | Evidence-grounded local answer generation or OpenAI-compatible chat completion with provider/model/token metadata |
| PostgreSQL | Documents, chunks, incidents, conversations, messages, retrieval events, and evaluation runs |
| pgvector | Vector storage and cosine-distance candidate retrieval |
| PostgreSQL FTS | Exact identifiers, error strings, paths, class names, and keyword retrieval |
| Redis | Async ingestion queue and short-lived ingestion-job state |
| Worker | Consumes Redis jobs, reports progress, retries failures up to three attempts, and persists parsed/embedded documents |
| Terraform/AWS | ECR, S3, RDS PostgreSQL, ElastiCache Redis, ECS Fargate, and ALB infrastructure |

## End-to-end data flows

### Ingestion flow

```text
Document/file/repository
        |
        v
Format-aware parser
        |
        v
Text normalization and overlapping chunking
        |
        v
Source metadata: path, format, service, URI, commit SHA
        |
        v
Embedding generation
        |
        v
documents + chunks + vector column in PostgreSQL
```

Supported parser inputs include plain text, Markdown, HTML, PDF, logs, incident
reports, and local repository snapshots. The browser currently loads text-based
files directly; PDF parsing is available in the backend parser and can be exposed
through a multipart upload endpoint in a future UI phase.

### Retrieval and answer flow

```text
Question
  |
  v
LangGraph query analyzer
  |----------------------|
  v                      v
Code-search tool      Hybrid retrieval
                         |---------|
                         v         v
                   pgvector      PostgreSQL FTS
                         \---------/
                              |
                              v
                  Reciprocal-rank fusion
                              |
                              v
                    Grounded provider/local answer
                              |
                              v
                    Citation ID validation
                         |       |
                         |       v
                         |  One correction retry
                         |       |
                         +-------+
```

The workflow performs one bounded retrieval retry when no evidence is found and
one bounded answer correction when citations are missing or reference IDs outside
the retrieved evidence. Code-oriented questions are routed to the code-search
tool, incident questions to incident analysis, log questions to log search, and
other questions to hybrid retrieval. The citation check validates citation IDs
against retrieved chunks; it is not a full natural-language entailment model.

Every chat response can expose the request ID, selected route/tool, retrieval
latency, retry count, provider/model, estimated or provider-reported token count,
and citation-validation result. Assistant messages persist this observability
metadata alongside retrieval events.

### Async ingestion flow

```text
Frontend/API -> POST /ingestions -> Redis list
                                      |
                                      v
                                app.worker
                                      |
                                      v
                          parse -> chunk -> embed -> PostgreSQL
                                      |
                                      v
                         GET /ingestions/{job_id}
```

## Repository layout

```text
DevMind/
├── backend/
│   ├── app/
│   │   ├── graph/              # LangGraph state, tools, and workflow
│   │   ├── ingestion/          # Parsers, chunking, queues, bulk indexing
│   │   ├── embeddings/         # Local and OpenAI-compatible embedding providers
│   │   ├── llm/                # Grounded local and OpenAI-compatible generation
│   │   ├── persistence/        # SQLAlchemy models, database, services
│   │   ├── retrieval/          # Reranking and retrieval helpers
│   │   ├── data/evaluation/    # Versioned evaluation cases
│   │   ├── data/manual-test-docs/ # Small local test corpus
│   │   ├── main.py             # FastAPI application and request middleware
│   │   └── worker.py           # Redis-backed ingestion worker
│   ├── scripts/
│   │   ├── benchmark_ingestion.py
│   │   ├── generate_demo_corpus.py
│   │   └── run_evaluation.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   └── src/main.tsx            # React application and API integration
├── infra/
│   ├── postgres/init.sql
│   └── terraform/              # AWS infrastructure
├── .github/workflows/ci.yml
├── docker-compose.yml
└── README.md
```

## Data model

| Table | Purpose |
| --- | --- |
| `documents` | Source identity, source type, URI, metadata, content hash, and timestamp |
| `chunks` | Chunk content, ordinal, metadata, embedding, and document relation |
| `incidents` | Persisted structured incident analyses |
| `conversations` | Conversation identity and creation time |
| `messages` | User/assistant content, latency, estimated token count, and request observability metadata |
| `retrieval_events` | Retrieved chunk, score, rank, and retrieval method per assistant message |
| `evaluation_runs` | Dataset version, mode, summary metrics, and case-level results |

All async relationship reads use eager loading to avoid SQLAlchemy
`MissingGreenlet` failures.

## API surface

OpenAPI documentation is available at `http://localhost:8000/docs`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `POST` | `/documents` | Persist one document immediately |
| `GET` | `/documents` | List indexed documents |
| `POST` | `/repositories/index` | Index a local repository or corpus snapshot |
| `POST` | `/ingestions` | Queue one document through Redis |
| `GET` | `/ingestions/{job_id}` | Read async ingestion status |
| `POST` | `/search` | Semantic, keyword, or hybrid retrieval |
| `POST` | `/chat` | LangGraph grounded assistant |
| `GET` | `/conversations/{conversation_id}` | Read persisted conversation messages |
| `POST` | `/incidents/analyze` | Structured incident analysis |
| `POST` | `/evaluations/run` | Run stored evaluation cases |
| `GET` | `/evaluations/{run_id}` | Read an evaluation run |

## Local development

### Prerequisites

- Windows PowerShell, macOS, or Linux
- Python 3.12+
- `uv`
- Node.js 22+
- Docker Desktop
- Docker Compose

### Start infrastructure

```powershell
cd D:\DevMind
docker compose up -d postgres redis
```

### Start the API

```powershell
cd D:\DevMind\backend
$env:PERSISTENCE_ENABLED="true"
$env:DATABASE_URL="postgresql+asyncpg://devmind:devmind@localhost:5432/devmind"
$env:REDIS_URL="redis://localhost:6379/0"
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

### Start the worker

In a second terminal:

```powershell
cd D:\DevMind\backend
$env:PERSISTENCE_ENABLED="true"
$env:DATABASE_URL="postgresql+asyncpg://devmind:devmind@localhost:5432/devmind"
$env:REDIS_URL="redis://localhost:6379/0"
uv run python -m app.worker
```

### Start the frontend

In a third terminal:

```powershell
cd D:\DevMind\frontend
npm ci
npm run dev
```

Open:

- UI: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`

## Local test workflow

### Index the included manual corpus

In the frontend, enter:

```text
D:\DevMind\backend\data\manual-test-docs
```

Click **Index snapshot**. The corpus contains payment incident, database runbook,
OAuth security, deployment, and log fixtures.

Or use the API:

```powershell
$body = @{
  path = "D:\DevMind\backend\data\manual-test-docs"
  batch_size = 100
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/repositories/index `
  -ContentType "application/json" `
  -Body $body
```

Indexing the same folder again should report duplicates rather than creating
additional documents.

### Generate and index 1,000 documents

```powershell
cd D:\DevMind
uv run --directory backend python -m scripts.generate_demo_corpus `
  backend/data/demo-corpus --documents 1000
```

When the API is running locally, enter this path in the frontend:

```text
D:\DevMind\backend\data\demo-corpus
```

The Docker API container cannot access arbitrary Windows host paths unless they
are mounted. For repository indexing, run the API with `uv` as shown above or
add an explicit Compose volume mount.

### Run the ingestion benchmark

After PostgreSQL is available, this command generates and indexes the requested
corpus through the same parser, chunker, embedding, and persistence pipeline:

```powershell
uv run --directory backend python -m scripts.benchmark_ingestion `
  backend/data/benchmark-corpus `
  --documents 1000 `
  --output backend/data/evaluation/ingestion-report.json
```

The JSON report records discovered/indexed/duplicate/failed documents, database
document and chunk totals, total ingestion time, measured embedding time, average
processing time, and a second duplicate-detection pass. The benchmark runs the
bulk pipeline directly; Redis queue throughput is a separate operational concern
and is not silently represented as part of these timings.

Queued ingestion reports `queued`, `processing`, `retrying`, `completed`, or
`failed` status, a bounded progress percentage, and attempt count. Worker
failures are retried up to three attempts; final failures remain visible through
`GET /ingestions/{job_id}`.

### Configure real providers

The default configuration uses deterministic local embeddings and a local
evidence-grounded answer generator so tests and offline development remain
repeatable. Real OpenAI-compatible providers can be enabled without changing
retrieval or graph code. Docker Compose automatically reads these settings from
the root `.env` file:

```powershell
$env:EMBEDDING_PROVIDER="openai"
$env:EMBEDDING_MODEL="text-embedding-3-small"
$env:EMBEDDING_API_KEY="<set outside source control>"
$env:EMBEDDING_BASE_URL="https://api.openai.com/v1"
$env:EMBEDDING_DIMENSION="1536"
$env:LLM_PROVIDER="openai"
$env:LLM_MODEL="gpt-4o-mini"
$env:LLM_API_KEY="<set outside source control>"
$env:LLM_BASE_URL="https://api.openai.com/v1"
```

The same settings can be placed in `.env` before running:

```powershell
cd D:\DevMind
docker compose up -d --build --wait
```

Never commit `.env` or print its secret values. The provider integration uses
structured content parts for compatibility with OpenAI-compatible gateways and
surfaces provider HTTP failures instead of returning a fabricated successful
answer.

The current PostgreSQL schema uses 1,536-dimensional pgvector columns. A
different embedding dimension is rejected until the schema is migrated and
re-embedded. Provider and model metadata is stored with indexed chunks. Remote
provider failures are surfaced rather than silently converted into successful
answers.

Generated answers must cite IDs belonging to the retrieved evidence. Invalid or
missing citations trigger at most one corrective generation attempt; the graph
then returns the bounded result rather than looping indefinitely.

### Test the assistant

Use the frontend query box with:

```text
Why did the payment service fail after deployment?
```

Then click **Ask grounded assistant** and **Continue conversation**. The second
request reuses the returned conversation ID and verifies async-safe persistence.

## Testing and quality checks

### Backend

```powershell
cd D:\DevMind\backend
uv run --extra dev pytest
uv run --extra dev ruff check .
```

### Frontend

```powershell
cd D:\DevMind\frontend
npm run lint
npm run build
```

### Compose

```powershell
cd D:\DevMind
docker compose config
docker compose up -d --build --wait
docker compose ps
docker compose logs api
docker compose logs worker
```

Stop without deleting volumes:

```powershell
docker compose down
```

Use `docker compose down -v` only when intentionally resetting PostgreSQL and
Redis data.

## Evaluation

The versioned dataset contains 57 engineering questions in
[backend/data/evaluation/cases.jsonl](backend/data/evaluation/cases.jsonl).
Each case contains a question, expected sources, and key facts.

Run the API-backed evaluation after indexing matching documents:

```powershell
cd D:\DevMind
uv run --directory backend python -m scripts.run_evaluation `
  --dataset v1 --top-k 5 `
  --output backend/data/evaluation/report.json
```

The report measures:

- recall@5
- precision@5
- answer correctness
- citation accuracy
- hallucination rate
- average latency
- estimated token usage
- hybrid-versus-semantic recall comparison

The 90% recall claim must come from a measured report. It is not hard-coded in
the application.

### Latest measured local reports

The checked-in reports were generated on the local Docker PostgreSQL/pgvector
stack using the deterministic local embedding provider:

| Report | Measured result |
| --- | --- |
| Ingestion | 1,000 discovered and indexed, 0 failures, 1,005 total database documents, 1,005 chunks |
| Ingestion duration | 11,682.94 ms total; 171.94 ms embedding time; 11.68 ms average indexed document |
| Duplicate pass | 1,000 duplicates detected |
| Hybrid recall@5 | 0.4211 |
| Hybrid precision@5 | 0.0877 |
| Hybrid answer correctness | 0.6140 |
| Hybrid citation accuracy | 0.4386 |
| Hybrid hallucination rate | 0.3860 |
| Hybrid average latency | 21.24 ms |
| Hybrid average estimated tokens | 212.32 |
| Semantic recall@5 | 0.4211 |

The current measured report does **not** support a 90% recall@5 claim, and
hybrid retrieval did not outperform semantic retrieval on this run. See
[backend/data/evaluation/report.json](backend/data/evaluation/report.json) and
[backend/data/evaluation/ingestion-report.json](backend/data/evaluation/ingestion-report.json)
for the complete machine-readable results.

## AWS deployment

Terraform in [infra/terraform/](infra/terraform/) provisions:

- ECR repositories for API, worker, and frontend images
- S3 source-artifact bucket
- RDS PostgreSQL 16
- ElastiCache Redis 7
- ECS Fargate API and worker services
- Application Load Balancer
- Security groups and task execution role

### Validate infrastructure

Install Terraform, then:

```powershell
cd D:\DevMind\infra\terraform
terraform init
terraform fmt -check
terraform validate
```

Create a private variables file:

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
```

Set real image URLs and a strong database password in `terraform.tfvars`.
Never commit that file or AWS credentials.

### Build and publish images

```powershell
docker build -t devmind-api:latest backend
docker build -t devmind-worker:latest backend
docker build -t devmind-frontend:latest frontend
```

Tag and push the images to the ECR repository URLs created by Terraform, then:

```powershell
terraform plan
terraform apply
```

Retrieve the load-balancer URL:

```powershell
terraform output -raw api_url
```

The live-link claim should only be added after the deployed URL, ECS health,
database connectivity, Redis worker processing, and evaluation report have all
been verified.

## CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on pushes and pull
requests and validates:

- backend dependency synchronization
- backend tests
- Ruff
- frontend `npm ci`
- frontend production build

## Security and operational notes

- Do not commit `.env`, `terraform.tfvars`, AWS credentials, or database passwords.
- Replace the development database password before any AWS deployment.
- Restrict database and Redis security groups to application tasks in production.
- Add HTTPS/ACM and private subnets before exposing the AWS ALB publicly.
- Use a managed or self-hosted embedding model, a representative corpus, and a
  measured evaluation report before making production retrieval-quality claims.
- Add external embedding and LLM providers only through environment-backed
  configuration; never hard-code API keys.
- Keep evaluation reports versioned and reproducible.
