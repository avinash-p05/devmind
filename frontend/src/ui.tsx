import { Fragment, ReactNode } from "react";
import type { Citation } from "./api";

export const pct = (value: number | undefined) =>
  value === undefined ? "—" : `${Math.round(value * 100)}%`;

export const num = (value: number | undefined | null) =>
  value === undefined || value === null ? "—" : value.toLocaleString();

export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

/** Renders "[1]" markers as clickable chips that highlight the matching source. */
export function AnswerText({
  text,
  citations,
  onCite,
}: {
  text: string;
  citations: Citation[];
  onCite: (n: number) => void;
}) {
  const known = new Set(citations.map((c) => c.number));
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="answer-text">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (!match) return <Fragment key={i}>{part}</Fragment>;
        const n = Number(match[1]);
        return known.has(n) ? (
          <button className="cite-chip" key={i} onClick={() => onCite(n)} type="button">
            {n}
          </button>
        ) : (
          <span className="cite-chip cite-chip-invalid" key={i} title="Not a retrieved source">
            {n}
          </span>
        );
      })}
    </p>
  );
}

export function SourceList({ citations, active }: { citations: Citation[]; active?: number | null }) {
  if (citations.length === 0) return null;
  return (
    <ol className="source-list">
      {citations.map((c) => (
        <li className={active === c.number ? "active" : ""} id={`source-${c.number}`} key={c.number}>
          <span className="source-num">{c.number}</span>
          <span className="source-path">{c.path}</span>
          {c.metadata.service && <Badge>{c.metadata.service}</Badge>}
        </li>
      ))}
    </ol>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
