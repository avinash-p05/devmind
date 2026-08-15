import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ChangeEvent, FormEvent, useState } from "react";
import "./styles.css";

type SearchMode = "semantic" | "keyword" | "hybrid";

type SearchResult = {
  chunk_id: string;
  document_name: string;
  content: string;
  score: number;
  rank: number;
  retrieval_method: string;
  metadata: Record<string, string>;
};

type ChatResponse = {
  query: string;
  answer: string;
  route: string;
  confidence: string;
  evidence_sufficient: boolean;
  citations: Array<{ chunk_id: string; document_name: string; score: number; metadata: Record<string, string> }>;
  conversation_id?: string;
  message_id?: string;
};

type IncidentAnalysis = {
  service: string;
  severity: string;
  root_cause_hypothesis: string;
  evidence: Array<{ document_name: string; score: number }>;
  affected_component: string;
  recommended_next_steps: string[];
  confidence: string;
  route: string;
  unresolved_questions: string[];
};

type EvaluationRun = {
  id: string;
  dataset_version: string;
  mode: string;
  status: string;
  summary: Record<string, number>;
  results: Array<{ question: string; retrieval_recall: number; citation_accurate: boolean; latency_ms: number }>;
};

type IngestionJob = {
  id: string;
  status: string;
  document_id?: string;
  error?: string;
};

type DocumentSummary = {
  id: string;
  name: string;
  source_type: string;
  content_length: number;
  metadata: Record<string, string>;
  created_at: string;
};

type RepositoryIndexResponse = {
  path: string;
  discovered: number;
  indexed: number;
  skipped_duplicates: number;
  failed: number;
  errors: string[];
};

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [query, setQuery] = useState("connection pool exhausted");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [sourceName, setSourceName] = useState("payment-incident.md");
  const [sourceContent, setSourceContent] = useState("");
  const [sourceType, setSourceType] = useState("incident");
  const [repositoryPath, setRepositoryPath] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [message, setMessage] = useState("Ready for an engineering query");
  const [loading, setLoading] = useState(false);
  const [assistant, setAssistant] = useState<ChatResponse | null>(null);
  const [incidentService, setIncidentService] = useState("payment-service");
  const [incidentSeverity, setIncidentSeverity] = useState("high");
  const [incidentQuery, setIncidentQuery] = useState("Why did the payment service fail after deployment?");
  const [incident, setIncident] = useState<IncidentAnalysis | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationRun | null>(null);

  async function runSearch(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    setMessage("Searching indexed evidence...");
    try {
      const response = await fetch(`${apiBase}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, mode, top_k: 8 }),
      });
      if (!response.ok) throw new Error(`Search failed (${response.status})`);
      const data = await response.json();
      setResults(data.results);
      setMessage(`${data.results.length} evidence chunks returned`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function ingestSource(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    setMessage("Indexing source...");
    try {
      const response = await fetch(`${apiBase}/ingestions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: sourceName,
          source_type: sourceType,
          content: sourceContent,
          metadata: { path: sourceName },
        }),
      });
      if (!response.ok) throw new Error(`Indexing failed (${response.status})`);
      const job: IngestionJob = await response.json();
      let current = job;
      for (let attempt = 0; attempt < 20 && current.status === "queued"; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 250));
        const statusResponse = await fetch(`${apiBase}/ingestions/${job.id}`);
        if (!statusResponse.ok) throw new Error(`Ingestion status failed (${statusResponse.status})`);
        current = await statusResponse.json();
      }
      if (current.status === "processing") {
        for (let attempt = 0; attempt < 20 && current.status === "processing"; attempt += 1) {
          await new Promise((resolve) => setTimeout(resolve, 250));
          const statusResponse = await fetch(`${apiBase}/ingestions/${job.id}`);
          current = await statusResponse.json();
        }
      }
      if (current.status !== "completed") throw new Error(current.error ?? "Ingestion did not complete");
      setSourceContent("");
      await loadDocuments();
      setMessage(`${sourceName} indexed successfully`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Indexing failed");
    } finally {
      setLoading(false);
    }
  }

  async function loadDocuments() {
    const response = await fetch(`${apiBase}/documents`);
    if (!response.ok) throw new Error(`Document listing failed (${response.status})`);
    const data = await response.json();
    setDocuments(data.items);
  }

  async function selectSourceFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setSourceName(file.name);
    setMessage(`Loaded ${file.name}; submit to index it`);
    setSourceContent(await file.text());
  }

  async function indexRepository(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage("Indexing repository snapshot...");
    try {
      const response = await fetch(`${apiBase}/repositories/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: repositoryPath, batch_size: 100 }),
      });
      if (!response.ok) throw new Error(`Repository indexing failed (${response.status})`);
      const data: RepositoryIndexResponse = await response.json();
      await loadDocuments();
      setMessage(
        `${data.indexed} indexed · ${data.skipped_duplicates} duplicates · ${data.failed} failed`,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Repository indexing failed");
    } finally {
      setLoading(false);
    }
  }

  async function askAssistant() {
    setLoading(true);
    setMessage("Routing question through the evidence graph...");
    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 5 }),
      });
      if (!response.ok) throw new Error(`Assistant failed (${response.status})`);
      const data: ChatResponse = await response.json();
      setAssistant(data);
      setConversationId(data.conversation_id);
      setMessage(data.evidence_sufficient ? `Grounded via ${data.route}` : "Evidence is insufficient");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Assistant failed");
    } finally {
      setLoading(false);
    }

  }

  async function continueConversation() {
    if (!conversationId) return;
    setLoading(true);
    setMessage("Continuing the grounded conversation...");
    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 5, conversation_id: conversationId }),
      });
      if (!response.ok) throw new Error(`Conversation request failed (${response.status})`);
      const data: ChatResponse = await response.json();
      setAssistant(data);
      setConversationId(data.conversation_id);
      setMessage(`Conversation continued via ${data.route}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Conversation request failed");
    } finally {
      setLoading(false);
    }
  }

  async function analyzeIncident() {
    setLoading(true);
    setMessage("Analyzing incident evidence...");
    try {
      const response = await fetch(`${apiBase}/incidents/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: incidentQuery, service: incidentService, severity: incidentSeverity, top_k: 5 }),
      });
      if (!response.ok) throw new Error(`Incident analysis failed (${response.status})`);
      const data: IncidentAnalysis = await response.json();
      setIncident(data);
      setMessage(`${data.confidence} confidence incident analysis ready`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Incident analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function runEvaluation() {
    setLoading(true);
    setMessage("Running evaluation dataset...");
    try {
      const response = await fetch(`${apiBase}/evaluations/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_version: "v1", mode: "hybrid", top_k: 5 }),
      });
      if (!response.ok) throw new Error(`Evaluation failed (${response.status})`);
      const data: EvaluationRun = await response.json();
      setEvaluation(data);
      setMessage(`${data.summary.case_count ?? 0} evaluation cases completed`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Evaluation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">DEV/01 · INCIDENT INTELLIGENCE</p>
        <h1>DevMind</h1>
        <p className="lede">Grounded answers for the moments when engineering context is scattered everywhere.</p>
        <div className="status"><span /> {message}</div>
      </section>
      <section className="workspace-grid">
        <section className="tool-panel">
          <p className="eyebrow">01 · INGEST SOURCE</p>
          <h2>Give the system a useful lead.</h2>
          <label>Source name<input value={sourceName} onChange={(event) => setSourceName(event.target.value)} /></label>
          <label>Source type<select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
            <option value="document">document</option>
            <option value="repository">repository</option>
            <option value="log">log</option>
            <option value="incident">incident</option>
          </select></label>
          <label>Load local text file<input type="file" accept=".md,.txt,.html,.htm,.log,.json,.py,.ts,.tsx,.js,.sql,.yaml,.yml" onChange={selectSourceFile} /></label>
          <label>Incident or engineering text<textarea value={sourceContent} onChange={(event) => setSourceContent(event.target.value)} required placeholder="Paste a postmortem, stack trace, or runbook excerpt..." /></label>
          <button disabled={loading || !sourceContent.trim()} onClick={() => void ingestSource()} type="button">Index source <span>↗</span></button>
          <form className="repository-form" onSubmit={indexRepository}>
            <p className="eyebrow">02 · INDEX REPOSITORY</p>
            <label>Local repository or corpus path<input value={repositoryPath} onChange={(event) => setRepositoryPath(event.target.value)} placeholder="D:\DevMind\backend\data\demo-corpus" required /></label>
            <button disabled={loading || !repositoryPath.trim()} type="submit">Index snapshot <span>↗</span></button>
          </form>
          <div className="incident-tool">
            <p className="eyebrow">03 · ANALYZE INCIDENT</p>
            <label>Service<input value={incidentService} onChange={(event) => setIncidentService(event.target.value)} /></label>
            <label>Severity<select value={incidentSeverity} onChange={(event) => setIncidentSeverity(event.target.value)}><option>critical</option><option>high</option><option>medium</option><option>low</option></select></label>
            <label>Question<textarea value={incidentQuery} onChange={(event) => setIncidentQuery(event.target.value)} /></label>
            <button disabled={loading || !incidentQuery.trim()} onClick={analyzeIncident} type="button">Analyze incident <span>↗</span></button>
            {incident && <div className="incident-result">
              <div className="evidence-meta"><span>{incident.route}</span><strong>{incident.confidence} confidence</strong></div>
              <h3>Root-cause hypothesis</h3>
              <p>{incident.root_cause_hypothesis}</p>
              <h3>Recommended next steps</h3>
              <ul>{incident.recommended_next_steps.map((step) => <li key={step}>{step}</li>)}</ul>
              <small>{incident.evidence.length} supporting evidence item{incident.evidence.length === 1 ? "" : "s"}</small>
            </div>}
          </div>
        </section>
        <section className="tool-panel search-panel">
          <p className="eyebrow">02 · RETRIEVE EVIDENCE</p>
          <h2>Ask the knowledge base.</h2>
          <form className="search-form" onSubmit={runSearch}>
            <input aria-label="Search query" value={query} onChange={(event) => setQuery(event.target.value)} />
            <button disabled={loading || !query.trim()} type="submit">Search</button>
          </form>
          <div className="mode-switch" role="group" aria-label="Retrieval mode">
            {(["hybrid", "semantic", "keyword"] as SearchMode[]).map((option) => (
              <button className={mode === option ? "active" : ""} key={option} onClick={() => setMode(option)} type="button">{option}</button>
            ))}
          </div>
          <button className="assistant-button" disabled={loading || !query.trim()} onClick={askAssistant} type="button">Ask grounded assistant <span>↗</span></button>
          {conversationId && <button className="continue-button" disabled={loading || !query.trim()} onClick={continueConversation} type="button">Continue conversation <span>↗</span></button>}
          {assistant && <div className="assistant-answer">
            <div className="evidence-meta"><span>{assistant.route}</span><strong>{assistant.confidence} confidence</strong></div>
            <p>{assistant.answer}</p>
            <small>{assistant.citations.length} validated citation{assistant.citations.length === 1 ? "" : "s"}</small>
          </div>}
          <div className="results" aria-live="polite">
            {results.length === 0 ? <p className="empty-state">No evidence selected yet. Search the indexed workspace.</p> : results.map((result) => (
              <article className="evidence" key={result.chunk_id}>
                <div className="evidence-meta"><span>#{result.rank} · {result.retrieval_method}</span><strong>{result.score.toFixed(3)}</strong></div>
                <h3>{result.document_name}</h3>
                <p>{result.content}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="documents-panel">
          <div>
            <p className="eyebrow">05 · INDEXED WORKSPACE</p>
            <h2>What the assistant can see.</h2>
          </div>
          <button disabled={loading} onClick={() => loadDocuments().catch((error) => setMessage(error instanceof Error ? error.message : "Document listing failed"))} type="button">Refresh inventory</button>
          <div className="document-list">
            {documents.length === 0 ? <p className="empty-state">Refresh to inspect indexed documents.</p> : documents.slice(0, 12).map((document) => (
              <div className="document-row" key={document.id}>
                <strong>{document.name}</strong>
                <span>{document.source_type} · {document.content_length} chars</span>
              </div>
            ))}
          </div>
        </section>
      </section>
      <section className="evaluation-panel">
        <div>
          <p className="eyebrow">04 · EVALUATION</p>
          <h2>Measure the evidence.</h2>
          <p className="panel-copy">Run the versioned benchmark against the current hybrid retriever and inspect the cases that need better coverage.</p>
        </div>
        <button disabled={loading} onClick={runEvaluation} type="button">Run v1 benchmark <span>↗</span></button>
        {evaluation && <div className="evaluation-summary">
          <div><strong>{evaluation.summary.case_count ?? 0}</strong><span>cases</span></div>
          <div><strong>{Math.round((evaluation.summary.recall_at_k ?? 0) * 100)}%</strong><span>recall@5</span></div>
          <div><strong>{Math.round((evaluation.summary.citation_accuracy ?? 0) * 100)}%</strong><span>citation accuracy</span></div>
          <div><strong>{Math.round(evaluation.summary.avg_latency_ms ?? 0)}ms</strong><span>avg latency</span></div>
        </div>}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
