import { useEffect, useMemo, useState } from "react";
import { api, DocumentSummary, Stats } from "./api";
import { Badge, Empty } from "./ui";

const PAGE = 50;

export function InventoryTab({ stats, refreshKey }: { stats: Stats | null; refreshKey: number }) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [type, setType] = useState("all");
  const [filter, setFilter] = useState("");
  const [shown, setShown] = useState(PAGE);

  useEffect(() => {
    api<{ items: DocumentSummary[] }>("/documents?limit=5000")
      .then((data) => setDocuments([...data.items].sort((a, b) => a.path.localeCompare(b.path))))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load documents"));
  }, [refreshKey]);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return documents.filter(
      (d) =>
        (type === "all" || d.source_type === type) &&
        (!needle || d.path.toLowerCase().includes(needle) || (d.metadata.service ?? "").includes(needle)),
    );
  }, [documents, type, filter]);

  const types = Object.entries(stats?.by_source_type ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="inventory">
      <section className="card">
        <header className="card-head">
          <h3>Services</h3>
          <span className="card-note">from the <code>Service:</code> field extracted during ingestion</span>
        </header>
        <div className="service-chips">
          {stats?.services.map((s) => (
            <button className="chip" key={s.name} onClick={() => { setFilter(s.name); setShown(PAGE); }} type="button">
              {s.name} <span>{s.documents}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="card">
        <header className="card-head">
          <h3>Documents</h3>
          <div className="segmented">
            {[["all", documents.length] as [string, number], ...types].map(([t, count]) => (
              <button className={type === t ? "active" : ""} key={t} onClick={() => { setType(t); setShown(PAGE); }} type="button">
                {t} <span>{count}</span>
              </button>
            ))}
          </div>
        </header>
        <input
          className="filter"
          onChange={(e) => { setFilter(e.target.value); setShown(PAGE); }}
          placeholder="Filter by path or service…"
          value={filter}
        />
        {error && <div className="alert">{error}</div>}
        {!error && visible.length === 0 && <Empty>No documents match.</Empty>}
        <table className="doc-table">
          <thead>
            <tr><th>Path</th><th>Type</th><th>Service</th><th>Size</th></tr>
          </thead>
          <tbody>
            {visible.slice(0, shown).map((d) => (
              <tr key={d.id}>
                <td className="source-path">{d.path}</td>
                <td><Badge>{d.source_type}</Badge></td>
                <td>{d.metadata.service ?? "—"}</td>
                <td>{(d.content_length / 1000).toFixed(1)} kB</td>
              </tr>
            ))}
          </tbody>
        </table>
        {visible.length > shown && (
          <button className="ghost more" onClick={() => setShown(shown + PAGE)} type="button">
            Show more ({visible.length - shown} remaining)
          </button>
        )}
      </section>
    </div>
  );
}
