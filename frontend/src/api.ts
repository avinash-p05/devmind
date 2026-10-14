export const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type SearchMode = "hybrid" | "vector" | "keyword";

export type SearchResult = {
  chunk_id: string;
  document_name: string;
  path: string;
  content: string;
  score: number;
  similarity: number | null;
  rank: number;
  retrieval_method: string;
  metadata: Record<string, string>;
};

export type SearchResponse = {
  query: string;
  mode: string;
  top_similarity: number;
  results: SearchResult[];
};

export type Citation = {
  number: number;
  chunk_id: string;
  document_name: string;
  path: string;
  score: number;
  metadata: Record<string, string>;
};

export type ChatResponse = {
  query: string;
  answer: string;
  route: string;
  tools_used: string[];
  refused: boolean;
  confidence: "high" | "low";
  citations: Citation[];
  citation_validation_passed: boolean;
  top_similarity: number;
  llm_model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
};

export type IncidentAnalysis = {
  service: string;
  severity: string;
  root_cause_hypothesis: string;
  affected_component: string;
  recommended_next_steps: string[];
  unresolved_questions: string[];
  evidence: Citation[];
  retrieved: Citation[];
  confidence: "high" | "low";
  route: string;
  total_tokens: number;
};

export type IngestionJob = {
  id: string;
  status: "queued" | "processing" | "retrying" | "completed" | "failed";
  attempts: number;
  document_id: string | null;
  error: string | null;
};

export type DocumentSummary = {
  id: string;
  name: string;
  path: string;
  source_type: string;
  content_length: number;
  metadata: Record<string, string>;
  created_at: string;
};

export type RepositoryIndexResponse = {
  path: string;
  discovered: number;
  indexed: number;
  skipped_duplicates: number;
  failed: number;
  chunks: number;
  duration_ms: number;
  errors: string[];
};

type ModeMetrics = { recall_at_k: number; hit_rate_at_k: number; mrr: number };

export type Stats = {
  documents: number;
  chunks: number;
  characters: number;
  last_indexed_at: string | null;
  by_source_type: Record<string, number>;
  services: { name: string; documents: number }[];
  ingestion: { pending: number | null; jobs_by_status: Record<string, number> };
  providers: { llm_base_url: string; llm_model: string; embedding_provider: string };
  min_score: number;
  benchmark: {
    cases?: number;
    retrieval?: Partial<Record<SearchMode, ModeMetrics>>;
    agent?: {
      model: string | null;
      answer_correctness: number;
      citation_accuracy: number;
      correct_refusal_rate: number;
      false_refusal_rate: number;
      latency_ms_p50: number;
      avg_prompt_tokens: number;
      avg_completion_tokens: number;
    };
  } | null;
};

export type EvaluationRun = {
  id: string;
  mode: string;
  summary: Record<string, number>;
};

/** JSON request helper: throws the API's `detail` message on non-2xx responses. */
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // keep the status text
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
