import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, Stats } from "./api";
import { AskTab } from "./AskTab";
import { BenchmarkTab } from "./BenchmarkTab";
import { IncidentTab } from "./IncidentTab";
import { InventoryTab } from "./InventoryTab";
import { KnowledgeTab } from "./KnowledgeTab";
import { num, pct } from "./ui";
import "./styles.css";

const TABS = [
  { id: "ask", label: "Ask" },
  { id: "incident", label: "Incident analysis" },
  { id: "knowledge", label: "Add knowledge" },
  { id: "inventory", label: "Inventory" },
  { id: "benchmark", label: "Benchmark" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const TYPE_ORDER = ["document", "incident", "code", "log", "config"];

function timeAgo(iso: string | null) {
  if (!iso) return "never";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 1440) return `${Math.round(minutes / 60)} h ago`;
  return `${Math.round(minutes / 1440)} d ago`;
}

function StatsStrip({ stats }: { stats: Stats }) {
  const total = Object.values(stats.by_source_type).reduce((a, b) => a + b, 0) || 1;
  const types = [...Object.entries(stats.by_source_type)].sort(
    (a, b) => TYPE_ORDER.indexOf(a[0]) - TYPE_ORDER.indexOf(b[0]),
  );
  const jobs = stats.ingestion.jobs_by_status;
  const hybrid = stats.benchmark?.retrieval?.hybrid;
  return (
    <section className="stats">
      <div className="stat">
        <span className="stat-label">Indexed</span>
        <strong>{num(stats.documents)}</strong>
        <span className="stat-sub">documents · {num(stats.chunks)} chunks · {(stats.characters / 1e6).toFixed(1)} M chars</span>
      </div>
      <div className="stat stat-wide">
        <span className="stat-label">By source type</span>
        <div className="type-bar">
          {types.map(([type, count]) => (
            <span className={`seg seg-${type}`} key={type} style={{ flexGrow: count / total }} title={`${type}: ${count}`} />
          ))}
        </div>
        <div className="type-legend">
          {types.map(([type, count]) => (
            <span key={type}><i className={`dot seg-${type}`} />{type} <b>{count}</b></span>
          ))}
        </div>
      </div>
      <div className="stat">
        <span className="stat-label">Ingestion</span>
        <strong>{stats.ingestion.pending ?? "—"}</strong>
        <span className="stat-sub">
          queued · {jobs.completed ?? 0} done · {jobs.failed ?? 0} failed (24 h) · last {timeAgo(stats.last_indexed_at)}
        </span>
      </div>
      <div className="stat">
        <span className="stat-label">Services</span>
        <strong>{stats.services.length}</strong>
        <span className="stat-sub">with indexed docs</span>
      </div>
      <div className="stat">
        <span className="stat-label">Benchmark</span>
        <strong>{pct(hybrid?.recall_at_k)}</strong>
        <span className="stat-sub">
          recall@5 · answers {pct(stats.benchmark?.agent?.answer_correctness)} correct
        </span>
      </div>
    </section>
  );
}

function App() {
  const [tab, setTab] = useState<TabId>("ask");
  const [stats, setStats] = useState<Stats | null>(null);
  const [offline, setOffline] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const loadStats = useCallback(() => {
    api<Stats>("/stats")
      .then((s) => { setStats(s); setOffline(false); })
      .catch(() => setOffline(true));
  }, []);

  useEffect(() => {
    loadStats();
    const timer = setInterval(loadStats, 15000);
    return () => clearInterval(timer);
  }, [loadStats]);

  const onIndexed = () => { loadStats(); setRefreshKey((k) => k + 1); };
  const local = stats?.providers.llm_base_url.includes("11434") || stats?.providers.llm_base_url.includes("ollama");

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo">DM</span>
          <div>
            <h1>DevMind</h1>
            <p>Grounded answers across docs, code, config, logs and incident reports</p>
          </div>
        </div>
        <div className="status-pills">
          <span className={`pill ${offline ? "pill-bad" : "pill-good"}`}><i />{offline ? "API offline" : "API online"}</span>
          {stats && <span className="pill">LLM · {stats.providers.llm_model} ({local ? "Ollama" : "OpenAI"})</span>}
          {stats && <span className="pill">Embeddings · {stats.providers.embedding_provider === "local" ? "bge-small (local)" : "OpenAI"}</span>}
        </div>
      </header>

      {stats && <StatsStrip stats={stats} />}
      {offline && <div className="alert">Can't reach the API. Is <code>docker compose up</code> running?</div>}

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button aria-selected={tab === t.id} className={tab === t.id ? "active" : ""} key={t.id} onClick={() => setTab(t.id)} role="tab" type="button">
            {t.label}
          </button>
        ))}
      </nav>

      {/* Tabs stay mounted (just hidden) so answers and form input survive switching. */}
      <section className="tab-body" hidden={tab !== "ask"}><AskTab minScore={stats?.min_score ?? 0.6} /></section>
      <section className="tab-body" hidden={tab !== "incident"}><IncidentTab services={stats?.services.map((s) => s.name) ?? []} /></section>
      <section className="tab-body" hidden={tab !== "knowledge"}><KnowledgeTab onIndexed={onIndexed} /></section>
      <section className="tab-body" hidden={tab !== "inventory"}><InventoryTab refreshKey={refreshKey} stats={stats} /></section>
      <section className="tab-body" hidden={tab !== "benchmark"}><BenchmarkTab stats={stats} /></section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
