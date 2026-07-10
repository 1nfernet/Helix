import type { Example } from "../types";

interface Props {
  examples: Example[];
  selected: Set<number>;
  onToggle: (i: number) => void;
  onCompile: () => void;
  loading: boolean;
}

export function BatchEditor({ examples, selected, onToggle, onCompile, loading }: Props) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Batch</h2>
      </div>
      <div className="panel-body">
        <p className="hint" style={{ marginTop: 0 }}>
          Compile several specs at once — a multiplex / library run.
        </p>
        <div className="batch-list">
          {examples.map((ex, i) => (
            <label key={`${ex.name}.${ex.format}`} className="batch-item">
              <input type="checkbox" checked={selected.has(i)} onChange={() => onToggle(i)} />
              <span className="run-name">{ex.name}</span>
              <span className="run-meta">{ex.format}</span>
            </label>
          ))}
        </div>
        <button className="btn" onClick={onCompile} disabled={loading || selected.size === 0}>
          {loading ? "Compiling…" : `Compile ${selected.size}`}
        </button>
      </div>
    </section>
  );
}
