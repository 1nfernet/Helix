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
        <h3>Library</h3>
        <span className="grow" />
        <div className="seg" role="group" aria-label="Spec format">
          <button aria-pressed={format === "helix"} className={format === "helix" ? "active" : ""} onClick={() => onFormatChange("helix")}>
            Helix
          </button>
          <button aria-pressed={format === "yaml"} className={format === "yaml" ? "active" : ""} onClick={() => onFormatChange("yaml")}>
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

        <label className="field-label" htmlFor="lib-source">
          Base spec
        </label>
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
          id="lib-source"
          className="code"
          style={{ minHeight: 180 }}
          spellCheck={false}
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
        />

        <label className="field-label" htmlFor="lib-genes" style={{ marginTop: 14, display: "block" }}>
          Genes
        </label>
        <textarea
          id="lib-genes"
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
