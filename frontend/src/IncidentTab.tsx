import { FormEvent, useState } from "react";
import { api, IncidentAnalysis } from "./api";
import { INCIDENT_EXAMPLES } from "./examples";
import { AnswerText, Badge, SourceList } from "./ui";

export function IncidentTab({ services }: { services: string[] }) {
  const [service, setService] = useState(INCIDENT_EXAMPLES[0].service);
  const [severity, setSeverity] = useState(INCIDENT_EXAMPLES[0].severity);
  const [query, setQuery] = useState(INCIDENT_EXAMPLES[0].query);
  const [result, setResult] = useState<IncidentAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<number | null>(null);

  async function analyze(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api<IncidentAnalysis>("/incidents/analyze", { query, service, severity, top_k: 5 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="two-col">
      <form className="card form-card" onSubmit={analyze}>
        <h3>Describe the incident</h3>
        <p className="card-note">The agent searches incident reports, logs and code, then proposes a root cause with citations.</p>
        <div className="form-row">
          <label>
            Service
            <input list="services" onChange={(e) => setService(e.target.value)} value={service} />
            <datalist id="services">{services.map((s) => <option key={s} value={s} />)}</datalist>
          </label>
          <label>
            Severity
            <select onChange={(e) => setSeverity(e.target.value)} value={severity}>
              {["SEV-1", "SEV-2", "SEV-3", "SEV-4"].map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
        </div>
        <label>
          What is happening?
          <textarea onChange={(e) => setQuery(e.target.value)} rows={4} value={query} />
        </label>
        <button className="primary" disabled={loading || !query.trim() || !service.trim()} type="submit">
          {loading ? "Analyzing…" : "Analyze incident"}
        </button>
        <div className="example-chips stacked">
          <span className="example-caption">Try:</span>
          {INCIDENT_EXAMPLES.map((ex) => (
            <button
              className="chip"
              key={ex.query}
              onClick={() => { setService(ex.service); setSeverity(ex.severity); setQuery(ex.query); }}
              type="button"
            >
              <strong>{ex.service}</strong> · {ex.query}
            </button>
          ))}
        </div>
      </form>

      <section className="card">
        <header className="card-head">
          <h3>Analysis</h3>
          {result && (
            <div className="badges">
              <Badge tone={result.confidence === "high" ? "good" : "warn"}>{result.confidence} confidence</Badge>
              <Badge>{result.total_tokens.toLocaleString()} tokens</Badge>
            </div>
          )}
        </header>
        {error && <div className="alert">{error}</div>}
        {loading && <div className="skeleton"><span /><span /><span /><span /></div>}
        {!result && !loading && !error && <p className="empty">Results appear here.</p>}
        {result && (
          <div className="analysis">
            <h4>Root-cause hypothesis</h4>
            <AnswerText citations={result.evidence} onCite={setActiveSource} text={result.root_cause_hypothesis} />
            <h4>Affected component</h4>
            <p>{result.affected_component}</p>
            {result.recommended_next_steps.length > 0 && (
              <>
                <h4>Recommended next steps</h4>
                <ul>{result.recommended_next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
              </>
            )}
            {result.unresolved_questions.length > 0 && (
              <>
                <h4>Open questions</h4>
                <ul>{result.unresolved_questions.map((s) => <li key={s}>{s}</li>)}</ul>
              </>
            )}
            {result.evidence.length > 0 ? (
              <>
                <h4>Cited evidence</h4>
                <SourceList active={activeSource} citations={result.evidence} />
              </>
            ) : (
              <>
                <h4>Retrieved evidence (not cited by the model)</h4>
                <SourceList citations={result.retrieved} />
              </>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
