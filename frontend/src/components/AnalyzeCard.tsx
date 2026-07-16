import { useState } from "react";
import { analyzeReads, exampleReads } from "../api";
import type { AnalyzeResult, ResolvedDesign } from "../types";

export function AnalyzeCard({ design }: { design: ResolvedDesign }) {
  const [reads, setReads] = useState("");
  const [res, setRes] = useState<AnalyzeResult | null>(null);
  const [busy, setBusy] = useState<"" | "load" | "run">("");
  const [err, setErr] = useState("");

  const loadExample = async () => {
    setBusy("load");
    setErr("");
    try {
      setReads((await exampleReads(design)).reads);
    } catch (e: unknown) {
      setErr((e as { message?: string })?.message || "could not generate reads");
    } finally {
      setBusy("");
    }
  };

  const run = async () => {
    if (!reads.trim() || busy) return;
    setBusy("run");
    setErr("");
    try {
      setRes(await analyzeReads(design, reads));
    } catch (e: unknown) {
      setErr((e as { message?: string })?.message || "analysis failed");
      setRes(null);
    } finally {
      setBusy("");
    }
  };

  const a = res?.analysis;
  const r = res?.reconciliation;
  const maxCount = res && res.spectrum.length ? Math.max(...res.spectrum.map((s) => s.count)) : 1;

  return (
    <div className="delivery">
      <div className="results-head">
        <div className="section-label">Analyze results</div>
        <button className="linkbtn" onClick={loadExample} disabled={!!busy}>
          {busy === "load" ? "…" : "load example reads"}
        </button>
      </div>
      <textarea
        className="code reads-input"
        aria-label="Amplicon reads"
        spellCheck={false}
        placeholder="Paste amplicon reads — FASTQ, FASTA, or one sequence per line"
        value={reads}
        onChange={(e) => setReads(e.target.value)}
      />
      <div className="ai-row2">
        <button className="btn" onClick={run} disabled={!!busy || !reads.trim()}>
          {busy === "run" ? "Analyzing…" : "Analyze"}
        </button>
        <span className="hint">observed vs predicted</span>
      </div>
      {err && <div className="note" role="alert">{err}</div>}

      {a && r && (
        <div className="analysis-out">
          <div className="metric-row">
            <div className="metric">
              <span className="mv">{(a.editing_efficiency * 100).toFixed(0)}%</span>
              <span className="ml">edited</span>
            </div>
            <div className="metric">
              <span className="mv">{a.frameshift_fraction != null ? `${(a.frameshift_fraction * 100).toFixed(0)}%` : "—"}</span>
              <span className="ml">frameshift</span>
            </div>
            <div className="metric">
              <span className="mv">{a.reads_aligned}</span>
              <span className="ml">reads aligned</span>
            </div>
          </div>
          {res.spectrum.length > 0 && (
            <div className="spectrum">
              {res.spectrum.map((s) => (
                <div key={s.indel} className="spec-bar">
                  <span className="sb-l">{s.indel > 0 ? `+${s.indel}` : s.indel}</span>
                  <span className="sb-track">
                    <span style={{ width: `${(s.count / maxCount) * 100}%` }} />
                  </span>
                  <span className="sb-c">{s.count}</span>
                </div>
              ))}
            </div>
          )}
          {r.notes.map((n, i) => {
            const cls = /agrees/.test(n)
              ? "note ok"
              : /DIVERGES|Low observed|WARNING/i.test(n)
                ? "note"
                : "hint recon-note";
            return (
              <div key={i} className={cls} style={{ marginTop: 6 }}>
                {n}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
