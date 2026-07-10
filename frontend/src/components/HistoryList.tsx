import type { RunSummary } from "../types";

interface Props {
  runs: RunSummary[];
  onSelect: (id: string) => void;
  onClear: () => void;
  limit?: number; // show only the N most recent (compact sidebar list)
  onViewAll?: () => void;
  title?: string;
}

export function HistoryList({ runs, onSelect, onClear, limit, onViewAll, title = "Recent runs" }: Props) {
  if (!runs.length) return null;
  const shown = limit ? runs.slice(0, limit) : runs;
  return (
    <div className="history">
      <div className="results-head">
        <div className="section-label">{title}</div>
        <button className="linkbtn" onClick={onClear}>
          clear
        </button>
      </div>
      <div className="run-list">
        {shown.map((r) => (
          <button key={r.id} className="run-item" onClick={() => onSelect(r.id)} title={r.name}>
            <span className={"dot-i " + (r.feasible ? "ok" : "warn")} />
            <span className="run-name">{r.name}</span>
            <span className="run-meta">
              {r.modality}
              {r.delivery ? ` · ${r.delivery}` : ""}
            </span>
          </button>
        ))}
      </div>
      {limit && runs.length > limit && onViewAll && (
        <button className="linkbtn view-all" onClick={onViewAll}>
          View all {runs.length} →
        </button>
      )}
    </div>
  );
}
