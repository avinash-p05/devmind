import { ChangeEvent, FormEvent, useState } from "react";
import { api, IngestionJob, RepositoryIndexResponse } from "./api";
import { Badge } from "./ui";

const STEPS: IngestionJob["status"][] = ["queued", "processing", "completed"];
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function KnowledgeTab({ onIndexed }: { onIndexed: () => void }) {
  const [name, setName] = useState("runbooks/my-runbook.md");
  const [sourceType, setSourceType] = useState("");
  const [content, setContent] = useState("");
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [folder, setFolder] = useState("/app/data/corpus");
  const [folderResult, setFolderResult] = useState<RepositoryIndexResponse | null>(null);
  const [folderError, setFolderError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setName(file.name);
    setContent(await file.text());
  }

  async function submitDocument(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setJobError(null);
    try {
      let current = await api<IngestionJob>("/ingestions", {
        name,
        content,
        source_type: sourceType || undefined,
      });
      setJob(current);
      // Poll the Redis-backed job until the worker finishes (or gives up after ~60 s).
      for (let i = 0; i < 120 && !["completed", "failed"].includes(current.status); i += 1) {
        await sleep(500);
        current = await api<IngestionJob>(`/ingestions/${current.id}`);
        setJob(current);
      }
      if (current.status === "completed") {
        setContent("");
        onIndexed();
      } else {
        setJobError(current.error ?? `Job is still ${current.status}. Is the worker running?`);
      }
    } catch (e) {
      setJobError(e instanceof Error ? e.message : "Ingestion failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitFolder(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFolderError(null);
    setFolderResult(null);
    try {
      setFolderResult(await api<RepositoryIndexResponse>("/repositories/index", { path: folder, batch_size: 64 }));
      onIndexed();
    } catch (e) {
      setFolderError(e instanceof Error ? e.message : "Indexing failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="two-col">
      <form className="card form-card" onSubmit={submitDocument}>
        <h3>Add a document</h3>
        <p className="card-note">
          Queued in Redis and indexed by the worker: parse → chunk → embed → store. The path decides
          the source type (e.g. <code>logs/</code>, <code>incidents/</code>, <code>.py</code>) unless you set it.
        </p>
        <div className="form-row">
          <label>
            Path / name
            <input onChange={(e) => setName(e.target.value)} required value={name} />
          </label>
          <label>
            Type
            <select onChange={(e) => setSourceType(e.target.value)} value={sourceType}>
              <option value="">auto-detect</option>
              {["document", "incident", "log", "code", "config"].map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
        </div>
        <label>
          Content
          <textarea
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste a runbook, postmortem, log excerpt or source file…"
            required
            rows={9}
            value={content}
          />
        </label>
        <div className="form-actions">
          <label className="file-button">
            Load file
            <input accept=".md,.txt,.log,.json,.yaml,.yml,.py,.ts,.tsx,.js,.sql,.html" onChange={loadFile} type="file" />
          </label>
          <button className="primary" disabled={busy || !content.trim() || !name.trim()} type="submit">
            Queue for indexing
          </button>
        </div>
        {job && (
          <div className="job">
            <div className="job-steps">
              {STEPS.map((step) => {
                const reached = STEPS.indexOf(job.status) >= STEPS.indexOf(step) || job.status === "completed";
                return <span className={reached ? "done" : ""} key={step}>{step}</span>;
              })}
              {job.status === "retrying" && <Badge tone="warn">retrying (attempt {job.attempts})</Badge>}
              {job.status === "failed" && <Badge tone="bad">failed</Badge>}
            </div>
            <small>job {job.id.slice(0, 8)} · attempts {job.attempts}</small>
          </div>
        )}
        {jobError && <div className="alert">{jobError}</div>}
      </form>

      <form className="card form-card" onSubmit={submitFolder}>
        <h3>Index a folder or repository</h3>
        <p className="card-note">
          Indexes every supported file under a path <strong>on the API server</strong>. In Docker the
          hand-written gold corpus is at <code>/app/data/corpus</code>. Unchanged files are skipped by content hash.
        </p>
        <label>
          Server path
          <input onChange={(e) => setFolder(e.target.value)} required value={folder} />
        </label>
        <button className="primary" disabled={busy || !folder.trim()} type="submit">Index folder</button>
        {folderError && <div className="alert">{folderError}</div>}
        {folderResult && (
          <dl className="trace">
            <div><dt>Discovered</dt><dd>{folderResult.discovered}</dd></div>
            <div><dt>Indexed</dt><dd>{folderResult.indexed}</dd></div>
            <div><dt>Duplicates skipped</dt><dd>{folderResult.skipped_duplicates}</dd></div>
            <div><dt>Failed</dt><dd>{folderResult.failed}</dd></div>
            <div><dt>Chunks</dt><dd>{folderResult.chunks}</dd></div>
            <div><dt>Time</dt><dd>{(folderResult.duration_ms / 1000).toFixed(1)} s</dd></div>
          </dl>
        )}
      </form>
    </div>
  );
}
