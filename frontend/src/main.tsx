import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">DEV/01 · INCIDENT INTELLIGENCE</p>
        <h1>DevMind</h1>
        <p className="lede">Grounded answers for the moments when engineering context is scattered everywhere.</p>
        <div className="status"><span /> API foundation online</div>
      </section>
      <section className="workspace-panel">
        <div>
          <p className="eyebrow">WORKSPACE</p>
          <h2>Knowledge graph initializing</h2>
          <p>Document ingestion, hybrid retrieval, and incident workflows will appear here as each milestone lands.</p>
        </div>
        <div className="panel-index"><strong>01</strong><span>foundation</span></div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
