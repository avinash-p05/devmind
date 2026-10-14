import { useState } from "react";
import { api, EvaluationRun, Stats } from "./api";
import { Empty, pct } from "./ui";

export function BenchmarkTab({ stats }: { stats: Stats | null }) {
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bench = stats?.benchmark;

  async function rerun() {
    setRunning(true);
    setError(null);
    try {
      setRun(await api<EvaluationRun>("/evaluations/run", { dataset_version: "v1", mode: "hybrid", top_k: 5, retrieval_only: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setRunning(false);
    }
  }

  if (!bench) return <Empty>No benchmark yet. Run <code>python scripts/evaluate.py</code> in the API container.</Empty>;

  const modes = [
    ["vector", "Vector only (pgvector)"],
    ["keyword", "Keyword only (Postgres FTS)"],
    ["hybrid", "Hybrid: RRF + rerank"],
  ] as const;

  return (
    <div className="two-col">
      <section className="card">
        <header className="card-head"><h3>Retrieval</h3><span className="card-note">{bench.cases} questions · top 5</span></header>
        <table className="metric-table">
          <thead><tr><th>Retriever</th><th>Recall@5</th><th>Hit@5</th><th>MRR</th></tr></thead>
          <tbody>
            {modes.map(([id, label]) => {
              const m = bench.retrieval?.[id];
              return (
                <tr className={id === "hybrid" ? "highlight" : ""} key={id}>
                  <td>{label}</td><td>{pct(m?.recall_at_k)}</td><td>{pct(m?.hit_rate_at_k)}</td><td>{m ? m.mrr.toFixed(2) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="card-note">
          Vector search handles paraphrase; keyword search handles exact identifiers like request IDs and
          config keys. Fusing both beats either alone.
        </p>
        <button className="ghost" disabled={running} onClick={() => void rerun()} type="button">
          {running ? "Running…" : "Re-run retrieval benchmark now (no LLM calls)"}
        </button>
        {error && <div className="alert">{error}</div>}
        {run && (
          <p className="card-note">
            Live run: recall@5 <strong>{pct(run.summary.recall_at_k)}</strong> · hit@5{" "}
            <strong>{pct(run.summary.hit_rate_at_k)}</strong> · MRR <strong>{run.summary.mrr?.toFixed(2)}</strong> · p50{" "}
            {run.summary.latency_ms_p50} ms
          </p>
        )}
      </section>

      <section className="card">
        <header className="card-head"><h3>Full agent</h3><span className="card-note">model: {bench.agent?.model ?? "—"}</span></header>
        {bench.agent ? (
          <>
            <div className="metric-grid">
              <div><strong>{pct(bench.agent.answer_correctness)}</strong><span>answer correctness</span></div>
              <div><strong>{pct(bench.agent.citation_accuracy)}</strong><span>citation accuracy</span></div>
              <div><strong>{pct(bench.agent.correct_refusal_rate)}</strong><span>unanswerable refused</span></div>
              <div><strong>{pct(bench.agent.false_refusal_rate)}</strong><span>false refusals</span></div>
              <div><strong>{(bench.agent.latency_ms_p50 / 1000).toFixed(1)} s</strong><span>p50 latency</span></div>
              <div><strong>{Math.round(bench.agent.avg_prompt_tokens + bench.agent.avg_completion_tokens).toLocaleString()}</strong><span>tokens / question</span></div>
            </div>
            <p className="card-note">
              Measured with <code>python scripts/evaluate.py</code>: every question runs through the LangGraph agent.
              It takes a few minutes with a local model, so it isn't run from the UI.
            </p>
          </>
        ) : (
          <Empty>Run <code>python scripts/evaluate.py</code> to measure the full agent.</Empty>
        )}
      </section>
    </div>
  );
}
