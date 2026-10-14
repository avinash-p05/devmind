import { FormEvent, useState } from "react";
import { api, ChatResponse, SearchMode, SearchResponse } from "./api";
import { EXAMPLE_GROUPS } from "./examples";
import { AnswerText, Badge, Empty, SourceList } from "./ui";

const MODES: { id: SearchMode; label: string }[] = [
  { id: "hybrid", label: "Hybrid" },
  { id: "vector", label: "Vector" },
  { id: "keyword", label: "Keyword" },
];

export function AskTab({ minScore }: { minScore: number }) {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [answer, setAnswer] = useState<ChatResponse | null>(null);
  const [evidence, setEvidence] = useState<SearchResponse | null>(null);
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<number | null>(null);

  async function loadEvidence(query: string, searchMode: SearchMode) {
    setSearching(true);
    try {
      setEvidence(await api<SearchResponse>("/search", { query, mode: searchMode, top_k: 5 }));
    } finally {
      setSearching(false);
    }
  }

  async function ask(text: string) {
    const query = text.trim();
    if (!query) return;
    setQuestion(query);
    setAsked(query);
    setLoading(true);
    setError(null);
    setAnswer(null);
    setActiveSource(null);
    try {
      // Retrieval is fast (~50 ms); show the evidence while the model is still answering.
      void loadEvidence(query, mode).catch(() => setEvidence(null));
      setAnswer(await api<ChatResponse>("/chat", { query, top_k: 5 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  function switchMode(next: SearchMode) {
    setMode(next);
    if (asked) void loadEvidence(asked, next).catch(() => setEvidence(null));
  }

  function cite(n: number) {
    setActiveSource(n);
    document.getElementById(`source-${n}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  const guardrailRefusal = answer?.refused && answer.total_tokens === 0;

  return (
    <div className="ask">
      <form className="ask-form" onSubmit={(e: FormEvent) => { e.preventDefault(); void ask(question); }}>
        <input
          aria-label="Question"
          autoFocus
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about an incident, a service, a config value or a code path…"
          value={question}
        />
        <button className="primary" disabled={loading || !question.trim()} type="submit">
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      <div className="examples">
        {EXAMPLE_GROUPS.map((group) => (
          <div className="example-group" key={group.label}>
            <div className="example-label">
              <strong>{group.label}</strong>
              <span>{group.hint}</span>
            </div>
            <div className="example-chips">
              {group.prompts.map((prompt) => (
                <button className="chip" disabled={loading} key={prompt} onClick={() => void ask(prompt)} type="button">
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {error && <div className="alert">{error}</div>}

      {(asked || answer) && (
        <div className="ask-results">
          <section className="card answer-card">
            <header className="card-head">
              <h3>Answer</h3>
              {answer && (
                <div className="badges">
                  <Badge tone={answer.confidence === "high" ? "good" : "warn"}>{answer.confidence} confidence</Badge>
                  <Badge>route: {answer.route}</Badge>
                </div>
              )}
            </header>

            {loading && <div className="skeleton"><span /><span /><span /></div>}

            {answer && (
              <>
                {guardrailRefusal && (
                  <div className="guardrail">
                    <strong>Guardrail: no LLM call made.</strong> Best similarity{" "}
                    {answer.top_similarity.toFixed(2)} is below MIN_SCORE {minScore.toFixed(2)}, so
                    nothing indexed is relevant enough to ground an answer.
                  </div>
                )}
                <AnswerText citations={answer.citations} onCite={cite} text={answer.answer} />
                <SourceList active={activeSource} citations={answer.citations} />

                <dl className="trace">
                  <div><dt>Tools</dt><dd>{answer.tools_used.join(", ")}</dd></div>
                  <div><dt>Top similarity</dt><dd>{answer.top_similarity.toFixed(2)} <small>(min {minScore.toFixed(2)})</small></dd></div>
                  <div><dt>Citations</dt><dd>{answer.citation_validation_passed ? "valid ✓" : "invalid ✗"}</dd></div>
                  <div><dt>Tokens</dt><dd>{answer.prompt_tokens.toLocaleString()} in · {answer.completion_tokens} out</dd></div>
                  <div><dt>Latency</dt><dd>{(answer.latency_ms / 1000).toFixed(1)} s</dd></div>
                  <div><dt>Model</dt><dd>{answer.total_tokens ? answer.llm_model : "not called"}</dd></div>
                </dl>
              </>
            )}
          </section>

          <section className="card evidence-card">
            <header className="card-head">
              <h3>Retrieved evidence</h3>
              <div className="segmented" role="group" aria-label="Retrieval mode">
                {MODES.map((m) => (
                  <button className={mode === m.id ? "active" : ""} key={m.id} onClick={() => switchMode(m.id)} type="button">
                    {m.label}
                  </button>
                ))}
              </div>
            </header>
            <p className="card-note">
              Top 5 chunks for the question. Switch modes to compare vector, keyword and hybrid retrieval.
            </p>
            {guardrailRefusal && evidence && (
              <div className="guardrail">
                Closest matches only: none reaches MIN_SCORE {minScore.toFixed(2)}, so none was sent to the model.
              </div>
            )}
            {searching && !evidence && <div className="skeleton"><span /><span /></div>}
            {evidence && evidence.results.length === 0 && <Empty>No chunks matched.</Empty>}
            <ol className={`evidence-list ${searching ? "dim" : ""}`}>
              {evidence?.results.map((r) => (
                <li key={r.chunk_id}>
                  <div className="evidence-head">
                    <span className="rank">#{r.rank}</span>
                    <span className="source-path">{r.path}</span>
                    <Badge tone={r.retrieval_method === "hybrid" ? "good" : "muted"}>{r.retrieval_method}</Badge>
                  </div>
                  <p>{r.content}</p>
                  <div className="evidence-scores">
                    score {r.score.toFixed(3)}
                    {r.similarity !== null && <> · cosine {r.similarity.toFixed(2)}</>}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </div>
  );
}
