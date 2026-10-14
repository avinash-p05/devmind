# DevMind Architecture

This document explains how the backend is put together and why. For setup and measured
results, see the [README](README.md).

## Module map

```text
backend/app/
  config.py              settings (env vars): providers, chunking, MIN_SCORE
  llm.py                 the only code that calls a model: chat() and embed() (Ollama / OpenAI)
  db.py                  SQLAlchemy models, pgvector + full-text indexes, sessions
  schemas.py             API request/response models
  main.py                FastAPI routes (thin: each route calls one service function)
  worker.py              Redis ingestion worker
  ingestion/
    parsers.py           file -> text + metadata, source-type classification
    chunking.py          overlapping, line-aware chunking
    pipeline.py          parse -> chunk -> embed (batched) -> store, with dedupe
    queue.py             Redis job queue and job state
  retrieval/
    hybrid.py            vector search, keyword search, fusion
    reranker.py          reciprocal rank fusion + term-coverage rerank
  agent/
    graph.py             LangGraph state machine
    tools.py             retrieval tools and the route -> tools table
    prompts.py           system prompt, templates, refusal text
    service.py           agent state -> API responses (chat, incident analysis)
  evaluation/
    metrics.py           metric definitions (pure functions)
    runner.py            runs the dataset through the retriever or the agent
backend/scripts/         generate_corpus.py, ingest.py, evaluate.py
backend/data/corpus/     hand-written gold sources
backend/data/evaluation/ v1.jsonl dataset and generated reports
```

## Data model

| Table | Key columns |
| --- | --- |
| `documents` | `path`, `source_type`, `content_hash` (unique, for idempotent re-ingestion), `metadata` |
| `chunks` | `content`, `path`, `source_type`, `embedding vector(384)` with an HNSW cosine index, `search_vector tsvector` (generated from content + path) with a GIN index |
| `evaluation_runs` | dataset, mode, summary, per-question results |

`path` and `source_type` are copied onto each chunk, so retrieval can filter (e.g. code only)
and cite without a join.

## Request lifecycle: `POST /chat`

1. `route_question` classifies the question with regexes, e.g. "implemented / configured /
   .yaml" -> `code`, "incident / rollback / failed" -> `incident`.
2. `retrieve` runs that route's tools concurrently. Each tool is the hybrid retriever
   scoped to source types. The general knowledge-base search always runs too, so a question
   that spans code and docs finds both. The tool rankings are fused with RRF.
3. The guardrail compares the best cosine similarity with `MIN_SCORE`. Below it, the agent
   returns a refusal and **no LLM call is made**.
4. `generate` builds a prompt from the numbered sources and calls `llm.chat()` in a worker
   thread.
5. `validate_citations` parses `[n]` markers. Missing or out-of-range citations trigger one
   correction call that shows the model its previous answer. A plain "I don't know" counts
   as a refusal.
6. The response includes the answer, only the sources actually cited, the route and tools,
   the top similarity, prompt/completion tokens and latency.

## Design decisions

**Why hybrid retrieval?** Engineering questions mix natural language with exact
identifiers. Embeddings handle paraphrase but blur `req-7f3a91` or `DB_POOL_SIZE` into
nearby tokens; full-text search is exact but misses synonyms. On the eval set, vector-only
recall@5 is 0.92 and keyword-only is 0.69. The hybrid reaches 0.96.

**Why RRF rather than adding the scores?** Cosine similarity (0-1) and `ts_rank_cd` (unbounded,
corpus-dependent) are on different scales, and any weighted sum needs re-tuning as the
corpus changes. RRF uses only rank positions. An earlier version weighted the vector leg
0.65 / keyword 0.35, which meant the 15th vector result outscored the 1st keyword result.
Equal weights fixed that.

**Why OR the keyword terms?** `plainto_tsquery` ANDs every word, so a full question matches only
chunks containing all of its words, which in practice is almost none. OR-ing the stemmed,
stopword-free terms and ranking with `ts_rank_cd` returns chunks that match more terms first.

**Why a rerank stage after fusion?** RRF knows positions, not content. Scoring the fused
candidates by how much of the question each chunk covers promotes the chunk that answers
the whole question over one that matched a single strong term. It is lexical and costs
nothing. A cross-encoder is the next step (see README, limitations).

**Why index the file path?** "Which file / module / YAML..." questions are about names. The
path goes into the tsvector, and is prepended to the text before embedding.

**Why the similarity guardrail?** It is the cheapest correct answer to off-topic questions: no
tokens are spent and the model has no chance to hallucinate. Its limit is that an
in-domain but unanswerable question ("how is Kafka rebalancing tuned?") can clear the
threshold. The system prompt's "say you don't know" rule is the second line of defence, and
the eval measures both.

**Why number the citations instead of using chunk IDs?** Models copy `[3]` reliably and
mangle 36-character UUIDs. Validation is then a range check.

**Why a rule-based router?** Four routes, deterministic, zero latency and zero cost, and every
route also runs the general search, so a wrong route lowers ranking quality without losing
recall.

**Why local embeddings by default?** `bge-small-en-v1.5` (384 dimensions) runs on CPU, costs
nothing, and makes the project runnable without an API key. OpenAI `text-embedding-3-small`
is a config switch, called with `dimensions=384` so the schema stays the same. Changing the
model still needs a re-index and a `MIN_SCORE` re-calibration.

**Why batch embeddings during ingestion?** One model call per 64 chunks instead of per chunk.
The local model is CPU-bound, so batching amortizes the overhead. A remote API pays one HTTP
round trip per batch. A failing batch is rolled back and recorded without stopping the run.

## Failure handling

| Failure | Behaviour |
| --- | --- |
| LLM provider down or timing out | SDK retries (`max_retries=2`), then HTTP 503 "LLM provider unavailable" |
| Answer truncated at `max_completion_tokens` | logged as a warning |
| Bad citations | one correction retry, then `citation_validation_passed=false`, `confidence=low` |
| Weak retrieval | refusal, no LLM call |
| Ingestion job error | worker re-queues up to 3 attempts, then marks the job `failed` with the error |
| Duplicate content | skipped by content hash |
| Embedding dimension mismatch | raises immediately instead of writing bad vectors |
