import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { FormEvent, useState } from "react";
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

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [query, setQuery] = useState("connection pool exhausted");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [sourceName, setSourceName] = useState("payment-incident.md");
  const [sourceContent, setSourceContent] = useState("");
  const [message, setMessage] = useState("Ready for an engineering query");
  const [loading, setLoading] = useState(false);

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

  async function ingestSource(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage("Indexing source...");
    try {
      const response = await fetch(`${apiBase}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: sourceName,
          source_type: "incident",
          content: sourceContent,
          metadata: { path: sourceName, service: "payment-service" },
        }),
      });
      if (!response.ok) throw new Error(`Indexing failed (${response.status})`);
      setSourceContent("");
      setMessage(`${sourceName} indexed successfully`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Indexing failed");
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
        <form className="tool-panel" onSubmit={ingestSource}>
          <p className="eyebrow">01 · INGEST SOURCE</p>
          <h2>Give the system a useful lead.</h2>
          <label>Source name<input value={sourceName} onChange={(event) => setSourceName(event.target.value)} /></label>
          <label>Incident or engineering text<textarea value={sourceContent} onChange={(event) => setSourceContent(event.target.value)} required placeholder="Paste a postmortem, stack trace, or runbook excerpt..." /></label>
          <button disabled={loading || !sourceContent.trim()} type="submit">Index source <span>↗</span></button>
        </form>
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
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
