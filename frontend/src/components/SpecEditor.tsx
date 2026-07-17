import type { Example, Format } from "../types";
import { CodeEditor } from "./CodeEditor";
import { Segmented } from "./Segmented";

interface Props {
  examples: Example[];
  selectedIndex: number;
  onSelectExample: (index: number) => void;
  source: string;
  onSourceChange: (s: string) => void;
  format: Format;
  onFormatChange: (f: Format) => void;
  onCompile: () => void;
  loading: boolean;
  errorLine?: number;
}

function DslReference() {
  return (
    <details className="dsl-ref">
      <summary>Grammar reference</summary>
      <div className="dsl-ref-body">
        <pre className="dsl-skel">{`helix "name" {
  organism: human(GRCh38)
  cell_line: HEK293T
  target: gene(SYM) { … }
  strategy { … }
  constraints { … }
  simulate { … }
  deliver: rnp
  validate: amplicon_seq
}`}</pre>
        <dl>
          <dt>target</dt>
          <dd>
            <code>goal</code> knockout · <code>region</code> exon(2..4) · <code>sequence</code> "ACGT…" ·{" "}
            <code>edit</code> "C&gt;T @ 50" · <code>delete</code> "40..90" · <code>tss</code> 40 ·{" "}
            <code>frame</code> 0<span className="rh">← enables protein-consequence + silent PAM-block</span>
          </dd>
          <dt>strategy</dt>
          <dd>
            <code>modality</code> crispr_ko · base_edit · prime_edit · hdr · deletion · crispri · crispra
            <br />
            <code>enzyme</code> auto · SpCas9 · SaCas9 · Cas12a · SpG · SpRY · Cas9-NG ·{" "}
            <code>editor</code> CBE · ABE · CGBE · <code>donor</code> ssodn · dsdna
          </dd>
          <dt>constraints</dt>
          <dd>
            <code>guides.count</code> 3 · <code>on_target.min_efficiency</code> 0.5 ·{" "}
            <code>off_target.max_cfd</code> 0.2 · <code>gc.min</code>/<code>gc.max</code> ·{" "}
            <code>profile</code> strict|lenient|screen|quick
            <br />
            <code>avoid</code>: [ homopolymer(&gt;=4), self_complementary(&gt;=8), common_variant(&gt;=0.01),
            restriction_site(BsaI) ]
          </dd>
          <dt>simulate</dt>
          <dd>
            <code>sequence_provider</code> inline|ensembl|ncbi · <code>on_target</code> · <code>off_target</code> ·{" "}
            <code>variant_source</code> none|ensembl
          </dd>
        </dl>
      </div>
    </details>
  );
}

export function SpecEditor(props: Props) {
  const { examples, selectedIndex, onSelectExample, source, onSourceChange } = props;
  const { format, onFormatChange, onCompile, loading, errorLine } = props;

  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Spec</h3>
        <span className="grow" />
        <Segmented
          ariaLabel="Spec format"
          value={format}
          onChange={onFormatChange}
          options={[
            { value: "helix", label: "Helix" },
            { value: "yaml", label: "YAML" },
          ]}
        />
      </div>

      <div className="editor-controls">
        <select
          value={selectedIndex}
          onChange={(e) => onSelectExample(Number(e.target.value))}
          aria-label="example"
        >
          <option value={-1} disabled>
            Load an example…
          </option>
          {examples.map((ex, i) => (
            <option key={`${ex.name}.${ex.format}`} value={i}>
              {ex.name} · {ex.format}
            </option>
          ))}
        </select>
      </div>

      <div className="editor-wrap">
        <CodeEditor
          value={source}
          onChange={onSourceChange}
          format={format}
          errorLine={errorLine}
          placeholder={'helix "my_experiment" {\n  target: gene(TP53) { … }\n}'}
        />
        <DslReference />
      </div>

      <div className="editor-actions">
        <button className="btn" onClick={onCompile} disabled={loading || !source.trim()}>
          {loading ? "Compiling…" : "Compile"}
        </button>
        <span className="hint">⌘/Ctrl + Enter</span>
      </div>
    </section>
  );
}
