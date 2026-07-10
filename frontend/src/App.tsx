import { useCallback, useEffect, useRef, useState } from "react";
import {
  clearRuns,
  compile,
  compileBatch,
  compileLibrary,
  getAiConfigured,
  getExamples,
  getRun,
  getRuns,
  saveRun,
} from "./api";
import type {
  ApiError,
  BatchItemResult,
  CompileResult,
  Example,
  Format,
  ResolvedDesign,
  RunSummary,
} from "./types";
import { SpecEditor } from "./components/SpecEditor";
import { ResultsPanel } from "./components/ResultsPanel";
import type { PickMods } from "./components/DnaHelix";
import { AiPanel } from "./components/AiPanel";
import { GeneLookup } from "./components/GeneLookup";
import { ComparePanel } from "./components/ComparePanel";
import { ModelsPanel } from "./components/ModelsPanel";
import { HistoryList } from "./components/HistoryList";
import { BatchEditor } from "./components/BatchEditor";
import { BatchResults } from "./components/BatchResults";
import { LibraryEditor } from "./components/LibraryEditor";

type Mode = "single" | "batch" | "library" | "compare" | "models" | "history";

const svg = (children: JSX.Element) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);
const ICONS: Record<string, JSX.Element> = {
  design: svg(<><path d="M4 4c8 4 8 12 16 16" /><path d="M20 4C12 8 12 16 4 20" /><path d="M7 6h4M13 18h4M9 12h6" /></>),
  batch: svg(<><path d="M12 3l9 5-9 5-9-5 9-5z" /><path d="M3 12l9 5 9-5" /><path d="M3 16l9 5 9-5" /></>),
  library: svg(<><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>),
  compare: svg(<><rect x="3" y="4" width="7" height="16" rx="1" /><rect x="14" y="4" width="7" height="16" rx="1" /></>),
  models: svg(<><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6" /><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>),
  history: svg(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>),
};

function parseGenes(text: string): string[] {
  return [...new Set(text.split(/[\s,;]+/).map((g) => g.trim()).filter(Boolean))];
}

const TRANSITION: Record<string, string> = { A: "G", G: "A", C: "T", T: "C", N: "A" };
const BASES = ["A", "C", "G", "T"];
const BE_TARGET: Record<string, { base: string; product: string }> = {
  CBE: { base: "C", product: "T" },
  ABE: { base: "A", product: "G" },
  CGBE: { base: "C", product: "G" },
};

/** Rewrite the `edit:` line of a spec source (Helix or YAML), inserting one if absent. */
function setEditInSource(src: string, edit: string): string {
  if (/^\s*edit:.*$/m.test(src)) return src.replace(/^(\s*edit:).*$/m, `$1 "${edit}"`);
  // Insert into a Helix `target: gene(SYM) {` block…
  const hx = src.match(/^(\s*)target:\s*gene\([^)]*\)\s*\{.*$/m);
  if (hx) return src.replace(hx[0], `${hx[0]}\n${hx[1]}  edit: "${edit}"`);
  // …or a YAML `target:` mapping.
  const ym = src.match(/^(\s*)target:\s*$/m);
  if (ym) return src.replace(ym[0], `${ym[0]}\n${ym[1]}  edit: "${edit}"`);
  return src;
}

/** Retarget the spec to a resolved gene: update the gene name, the experiment
 * name/comments, write its sequence, and switch to the inline provider. */
function setResolvedGeneInSource(src: string, gene: string, seq: string): string {
  let s = src;
  const oldMatch = src.match(/gene\(\s*([^)\s]+)\s*\)/) || src.match(/^\s*gene:\s*(\S+)/m);
  const oldGene = oldMatch ? oldMatch[1] : "";
  // 1) gene name in the target block
  if (/gene\(\s*[^)]*\)/.test(s)) s = s.replace(/gene\(\s*[^)]*\)/, `gene(${gene})`);
  else if (/^\s*gene:\s*\S+/m.test(s)) s = s.replace(/(^\s*gene:\s*)\S+/m, `$1${gene}`);
  // 1b) swap the old symbol for the new one in the experiment name + comments only
  //     (plain substring swap — safe: the DNA sequence never contains a gene symbol).
  if (oldGene && oldGene !== gene) {
    const swap = (t: string) => t.split(oldGene).join(gene);
    s = s.replace(/(^\s*helix\s+")([^"]*)(")/m, (_m, a, n, b) => a + swap(n) + b);
    s = s.replace(/(^\s*name:\s*"?)([^"\n]*)/m, (_m, a, n) => a + swap(n));
    s = s.replace(/^(\s*#.*)$/gm, (m) => swap(m));
  }
  // 2) sequence — replace an existing line, else insert into the target block
  if (/^\s*sequence:.*$/m.test(s)) {
    s = s.replace(/^(\s*sequence:).*$/m, `$1 "${seq}"`);
  } else {
    const hx = s.match(/^(\s*)target:\s*gene\([^)]*\)\s*\{.*$/m); // Helix target block
    const ym = hx ? null : s.match(/^(\s*)target:\s*$/m); // YAML target mapping
    const m = hx ?? ym;
    if (m) s = s.replace(m[0], `${m[0]}\n${m[1]}  sequence: "${seq}"`);
  }
  if (/sequence_provider:\s*\w+/.test(s)) s = s.replace(/(sequence_provider:\s*)\w+/, "$1inline");
  return s;
}

/** Parse `edit: "X>Y @ N"` -> {ref, alt, pos0}. */
function parseEditStr(src: string): { ref: string; alt: string; pos0: number } | null {
  const m = src.match(/edit:\s*"([ACGTN-]+)>([ACGTN-]+)\s*@\s*(\d+)"/i);
  return m ? { ref: m[1].toUpperCase(), alt: m[2].toUpperCase(), pos0: parseInt(m[3], 10) - 1 } : null;
}

/** Next substitution base, cycling through the three non-reference bases. */
function cycleAlt(ref: string, curAlt: string): string {
  const opts = BASES.filter((b) => b !== ref);
  return opts[(opts.indexOf(curAlt) + 1) % opts.length];
}

/** The base-editor chemistry in force for a base-edit design, if any. */
function editorOf(d: CompileResult["design"]): "CBE" | "ABE" | null {
  const be = d.selected?.[0]?.base_edit ?? d.guides?.[0]?.base_edit;
  return (be?.editor as "CBE" | "ABE") ?? null;
}

/** Compute the new `edit` string a pick should install, or null if the base is not editable here. */
function nextEditFor(
  d: CompileResult["design"],
  src: string,
  index: number,
  mods: { shift: boolean }
): string | null {
  const seq = (d.target?.sequence ?? "").toUpperCase();
  const ref = seq[index] ?? "N";
  if (d.modality === "prime_edit" || d.modality === "hdr") {
    if (mods.shift) {
      // Cycle the substituted base of the current edit (position unchanged, so the
      // helix doesn't recenter) — repeated shift-clicks step through the alternatives.
      const cur = parseEditStr(src);
      if (cur) return `${cur.ref}>${cycleAlt(cur.ref, cur.alt)} @ ${cur.pos0 + 1}`;
      return `${ref}>${cycleAlt(ref, ref)} @ ${index + 1}`;
    }
    return `${ref}>${TRANSITION[ref] ?? "A"} @ ${index + 1}`;
  }
  if (d.modality === "base_edit") {
    const ed = editorOf(d);
    if (!ed) return null;
    const { base, product } = BE_TARGET[ed];
    if (ref !== base) return null; // CBE edits C, ABE edits A
    return `${base}>${product} @ ${index + 1}`;
  }
  return null;
}
export default function App() {
  const [examples, setExamples] = useState<Example[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [source, setSource] = useState("");
  const [format, setFormat] = useState<Format>("helix");
  const [result, setResult] = useState<CompileResult | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);

  const [mode, setMode] = useState<Mode>("single");
  const [aiConfigured, setAiConfigured] = useState(false);
  const [aiDemo, setAiDemo] = useState(false);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [cmpA, setCmpA] = useState("");
  const [cmpB, setCmpB] = useState("");
  const [cmpDesignA, setCmpDesignA] = useState<ResolvedDesign | null>(null);
  const [cmpDesignB, setCmpDesignB] = useState<ResolvedDesign | null>(null);
  const [batchSel, setBatchSel] = useState<Set<number>>(new Set());
  const [batchResults, setBatchResults] = useState<BatchItemResult[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);

  const [libIndex, setLibIndex] = useState(-1);
  const [libSource, setLibSource] = useState("");
  const [libFormat, setLibFormat] = useState<Format>("helix");
  const [libGenes, setLibGenes] = useState("TP53, EGFR, KRAS");
  const [libResults, setLibResults] = useState<BatchItemResult[]>([]);
  const [libLoading, setLibLoading] = useState(false);

  // Mirror `source` in a ref so a fast 3D sweep can build each step on the last
  // without waiting for a React re-render between pointer moves.
  const sourceRef = useRef(source);
  useEffect(() => {
    sourceRef.current = source;
  }, [source]);

  useEffect(() => {
    getExamples()
      .then((ex) => {
        setExamples(ex);
        if (!ex.length) return;
        const idx = ex.findIndex((e) => e.name === "tp53_ko" && e.format === "helix");
        const pick = idx >= 0 ? idx : 0;
        setSelectedIndex(pick);
        setSource(ex[pick].source);
        setFormat(ex[pick].format);
        setBatchSel(new Set(ex.map((_, i) => i).filter((i) => ex[i].format === "helix")));
        setLibIndex(pick);
        setLibSource(ex[pick].source);
        setLibFormat(ex[pick].format);
      })
      .catch(() => setError({ type: "network", message: "Could not reach the Helix API (is `helix serve` running?)" }));
  }, []);

  useEffect(() => {
    getRuns().then(setHistory).catch(() => {});
    getAiConfigured()
      .then(({ configured, demo }) => {
        setAiConfigured(configured);
        setAiDemo(demo);
      })
      .catch(() => {});
  }, []);

  // Drop an AI-drafted spec into the editor (user reviews, then compiles).
  function draftInto(src: string, fmt: Format) {
    setSelectedIndex(-1);
    setSource(src);
    sourceRef.current = src;
    setFormat(fmt);
    setResult(null);
    setError(null);
  }

  // Apply a critique's revised spec and recompile it.
  const applySource = useCallback(
    (src: string) => {
      setSource(src);
      sourceRef.current = src;
      setLoading(true);
      setError(null);
      compile(src, format)
        .then((r) => {
          setResult(r);
          pushHistory(r);
        })
        .catch((e) => setError(e as ApiError))
        .finally(() => setLoading(false));
    },
    [format]
  );

  function pushHistory(res: CompileResult) {
    saveRun(res)
      // The store coalesces repeat runs of one design (reusing its id); drop any
      // existing entry with that id so the updated run moves to the front, not dupes.
      .then((summary) => setHistory((prev) => [summary, ...prev.filter((r) => r.id !== summary.id)]))
      .catch(() => {});
  }

  const onCompile = useCallback(async () => {
    if (!source.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const r = await compile(source, format);
      setResult(r);
      pushHistory(r);
    } catch (e) {
      setError(e as ApiError);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [source, format, loading]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (mode === "single") onCompile();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onCompile, mode]);

  // Interactive edit: pick a base in the 3D helix -> rewrite target.edit.
  //  - click            place the edit (prime: transition; base-edit: C→T / A→G)
  //  - shift-click       cycle the substituted base (prime editing)
  //  - drag (sweep)      move the edit live along the helix; recompile on release
  const onPickBase = useCallback(
    (index: number, mods: PickMods) => {
      const d = result?.design;
      if (!d || !d.target) return;
      const edit = nextEditFor(d, sourceRef.current, index, mods);
      if (!edit) return; // base not editable in this modality/editor
      const newSource = setEditInSource(sourceRef.current, edit);
      if (newSource === sourceRef.current) return;
      sourceRef.current = newSource; // advance synchronously for the next sweep step
      setSource(newSource);
      if (mods.sweep) return; // live text only — don't rebuild the 3D mid-drag
      if (loading) return;
      setLoading(true);
      setError(null);
      compile(newSource, format)
        .then((r) => {
          setResult(r);
          pushHistory(r);
        })
        .catch((e) => setError(e as ApiError))
        .finally(() => setLoading(false));
    },
    [result, format, loading]
  );

  function selectExample(i: number) {
    const ex = examples[i];
    if (!ex) return;
    setSelectedIndex(i);
    setSource(ex.source);
    setFormat(ex.format);
    setResult(null);
    setError(null);
  }

  function toggleBatch(i: number) {
    setBatchSel((prev) => {
      const n = new Set(prev);
      if (n.has(i)) n.delete(i);
      else n.add(i);
      return n;
    });
  }

  async function runBatch() {
    const items = [...batchSel].map((i) => ({ source: examples[i].source, format: examples[i].format }));
    if (!items.length) return;
    setBatchLoading(true);
    try {
      const results = await compileBatch(items);
      setBatchResults(results);
      results.forEach((r) => r.design && r.protocol && pushHistory({ design: r.design, protocol: r.protocol }));
    } catch (e) {
      setBatchResults([{ name: null, error: (e as ApiError).message }]);
    } finally {
      setBatchLoading(false);
    }
  }

  function selectLibBase(i: number) {
    const ex = examples[i];
    if (!ex) return;
    setLibIndex(i);
    setLibSource(ex.source);
    setLibFormat(ex.format);
  }

  async function runLibrary() {
    const genes = parseGenes(libGenes);
    if (!genes.length || libLoading) return;
    setLibLoading(true);
    try {
      const results = await compileLibrary(libSource, libFormat, genes);
      setLibResults(results);
      results.forEach((r) => r.design && r.protocol && pushHistory({ design: r.design, protocol: r.protocol }));
    } catch (e) {
      setLibResults([{ name: null, error: (e as ApiError).message }]);
    } finally {
      setLibLoading(false);
    }
  }

  function openRun(res: CompileResult) {
    setMode("single");
    setResult(res);
    setError(null);
  }

  function clearHistory() {
    clearRuns()
      .then(() => setHistory([]))
      .catch(() => {});
  }

  function openHistory(id: string) {
    getRun(id).then(openRun).catch(() => {});
  }

  function onInsertSequence(seq: string, gene: string): "changed" | "same" | "notarget" {
    const ns = setResolvedGeneInSource(source, gene, seq);
    if (ns !== source) {
      sourceRef.current = ns;
      setSource(ns);
      setSelectedIndex(-1); // the spec is now edited — no longer the loaded example
      return "changed";
    }
    // no change: distinguish "already targeting this gene" from "no target block"
    return /gene\(\s*[^)]*\)/.test(source) || /^\s*target:/m.test(source) ? "same" : "notarget";
  }

  function onPickCompare(slot: "a" | "b", id: string) {
    const setId = slot === "a" ? setCmpA : setCmpB;
    const setDesign = slot === "a" ? setCmpDesignA : setCmpDesignB;
    setId(id);
    if (!id) return setDesign(null);
    getRun(id)
      .then((r) => setDesign(r.design))
      .catch(() => setDesign(null));
  }

  const historyPanel = (
    <HistoryList
      runs={history}
      onSelect={openHistory}
      onClear={clearHistory}
      limit={5}
      onViewAll={() => setMode("history")}
    />
  );

  const NAV: { id: Mode; label: string; icon: JSX.Element }[] = [
    { id: "single", label: "Design", icon: ICONS.design },
    { id: "batch", label: "Batch", icon: ICONS.batch },
    { id: "library", label: "Library", icon: ICONS.library },
    { id: "compare", label: "Compare", icon: ICONS.compare },
    { id: "models", label: "Models", icon: ICONS.models },
    { id: "history", label: "History", icon: ICONS.history },
  ];
  const HEAD: Record<Mode, { title: string; sub: string }> = {
    single: { title: "Design", sub: "Compose a spec, compile, and edit the guide or edit directly on the 3D helix." },
    batch: { title: "Batch", sub: "Compile many specs at once and compare feasibility side by side." },
    library: { title: "Library", sub: "Expand one base spec across a gene list into a per-gene design library." },
    compare: { title: "Compare", sub: "Put two saved designs side by side — differences are highlighted." },
    models: { title: "Models", sub: "The databases and simulation software Helix connects to, and their status." },
    history: { title: "History", sub: "Every compiled design, newest first — one entry per design, click to reopen." },
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h1 className="wordmark">
          <svg className="mark" width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M7 3c0 5 10 6 10 9s-10 4-10 9" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
            <path d="M17 3c0 5-10 6-10 9s10 4 10 9" stroke="var(--text)" strokeWidth="2" strokeLinecap="round" />
            <path d="M8.5 6.5h7M8.5 17.5h7M6.7 12h10.6" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span>Helix<span className="dot">.</span></span>
        </h1>
        <nav className="nav" aria-label="sections">
          {NAV.map((n) => (
            <button key={n.id} className={mode === n.id ? "active" : ""} onClick={() => setMode(n.id)}>
              {n.icon}
              <span>{n.label}</span>
              {n.id === "history" && history.length > 0 && <span className="nav-badge">{history.length}</span>}
            </button>
          ))}
        </nav>
        <span className="grow" />
        <div className="sidebar-foot">
          <span className={"ai-dot" + (aiDemo ? " demo" : aiConfigured ? " on" : "")} />
          AI {aiDemo ? "demo" : aiConfigured ? "ready" : "off"}
        </div>
      </aside>

      <main className="workspace">
        <div className="topbar">
          <h2>{HEAD[mode].title}</h2>
          <p>{HEAD[mode].sub}</p>
        </div>

        {mode === "models" && (
          <ModelsPanel
            provenance={result?.design.provenance.adapters}
            designName={result?.design.spec_name}
          />
        )}

        {mode === "compare" && (
          <ComparePanel
            runs={history}
            aId={cmpA}
            bId={cmpB}
            a={cmpDesignA}
            b={cmpDesignB}
            onPick={onPickCompare}
          />
        )}

        {mode === "history" && (
          <div className="history-page">
            {history.length ? (
              <HistoryList runs={history} onSelect={openHistory} onClear={clearHistory} title="All runs" />
            ) : (
              <div className="empty">
                <div className="big">No runs yet</div>
                Compile a design and it will appear here.
              </div>
            )}
          </div>
        )}

        {mode === "single" && (
          <div className="grid">
            <div className="col">
              <AiPanel
                configured={aiConfigured}
                demo={aiDemo}
                source={source}
                format={format}
                onDraft={draftInto}
                onApply={applySource}
              />
              <GeneLookup onInsert={onInsertSequence} />
              <SpecEditor
                examples={examples}
                selectedIndex={selectedIndex}
                onSelectExample={selectExample}
                source={source}
                onSourceChange={(s) => {
                  setSource(s);
                  setSelectedIndex(-1); // typing diverges from the loaded example
                }}
                format={format}
                onFormatChange={setFormat}
                onCompile={onCompile}
                loading={loading}
                errorLine={error?.line}
              />
              {historyPanel}
            </div>
            <ResultsPanel result={result} error={error} loading={loading} onPickBase={onPickBase} />
          </div>
        )}

        {mode === "batch" && (
          <div className="grid">
            <div className="col">
              <BatchEditor
                examples={examples}
                selected={batchSel}
                onToggle={toggleBatch}
                onCompile={runBatch}
                loading={batchLoading}
              />
              {historyPanel}
            </div>
            <BatchResults
              results={batchResults}
              loading={batchLoading}
              onOpen={(r) => r.design && r.protocol && openRun({ design: r.design, protocol: r.protocol })}
            />
          </div>
        )}

        {mode === "library" && (
          <div className="grid">
            <div className="col">
              <LibraryEditor
                examples={examples}
                baseIndex={libIndex}
                onSelectBase={selectLibBase}
                source={libSource}
                onSourceChange={setLibSource}
                format={libFormat}
                onFormatChange={setLibFormat}
                genes={libGenes}
                onGenesChange={setLibGenes}
                onCompile={runLibrary}
                loading={libLoading}
                geneCount={parseGenes(libGenes).length}
              />
              {historyPanel}
            </div>
            <BatchResults
              results={libResults}
              loading={libLoading}
              onOpen={(r) => r.design && r.protocol && openRun({ design: r.design, protocol: r.protocol })}
            />
          </div>
        )}
      </main>
    </div>
  );
}
