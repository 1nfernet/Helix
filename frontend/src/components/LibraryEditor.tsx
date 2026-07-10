import type { Example, Format } from "../types";

interface Props {
  examples: Example[];
  baseIndex: number;
  onSelectBase: (i: number) => void;
  source: string;
  onSourceChange: (s: string) => void;
  format: Format;
  onFormatChange: (f: Format) => void;
  genes: string;
  onGenesChange: (g: string) => void;
  onCompile: () => void;
  loading: boolean;
  geneCount: number;
}

export function LibraryEditor(props: Props) {
  const { examples, baseIndex, onSelectBase, source, onSourceChange } = props;
  const { format, onFormatChange, genes, onGenesChange, onCompile, loading, geneCount } = props;

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Library</h2>
        <span className="grow" />
        <div className="seg" role="tablist" aria-label="format">
          <button className={format === "helix" ? "active" : ""} onClick={() => onFormatChange("helix")}>
            Helix
          </button>
          <button className={format === "yaml" ? "active" : ""} onClick={() => onFormatChange("yaml")}>
            YAML
          </button>
        </div>
      </div>

      <div className="panel-body">
        <p className="hint" style={{ marginTop: 0 }}>
          One base spec, applied to every gene below — a knockout/edit library. Each gene is
          resolved from the database (an inline sequence is switched to Ensembl), so this needs
          network access.
        </p>

        <div className="field-label">Base spec</div>
        <select
          value={baseIndex}
          onChange={(e) => onSelectBase(Number(e.target.value))}
          aria-label="base spec"
          style={{ marginBottom: 10 }}
        >
          <option value={-1} disabled>
            Load a base spec…
          </option>
          {examples.map((ex, i) => (
            <option key={`${ex.name}.${ex.format}`} value={i}>
              {ex.name} · {ex.format}
            </option>
          ))}
        </select>
        <textarea
          className="code"
          style={{ minHeight: 180 }}
          spellCheck={false}
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
        />

        <div className="field-label" style={{ marginTop: 14 }}>
          Genes
        </div>
        <textarea
          className="code genes"
          spellCheck={false}
          placeholder="TP53, EGFR, KRAS, BRCA1"
          value={genes}
          onChange={(e) => onGenesChange(e.target.value)}
        />

        <button
          className="btn"
          style={{ marginTop: 14 }}
          onClick={onCompile}
          disabled={loading || geneCount === 0}
        >
          {loading ? "Compiling…" : `Compile library (${geneCount})`}
        </button>
      </div>
    </section>
  );
}
