import { useState } from "react";
import { resolveGene } from "../api";
import type { ResolveResult } from "../types";

export function GeneLookup({
  onInsert,
}: {
  onInsert: (sequence: string, gene: string) => "changed" | "same" | "notarget";
}) {
  const [gene, setGene] = useState("TP53");
  const [provider, setProvider] = useState("ensembl");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<ResolveResult | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const run = async () => {
    if (!gene.trim() || busy) return;
    setBusy(true);
    setErr("");
    setMsg("");
    setRes(null);
    try {
      setRes(await resolveGene(gene.trim(), "GRCh38", provider));
    } catch (e: unknown) {
      setErr((e as { message?: string })?.message || "Lookup failed");
    } finally {
      setBusy(false);
    }
  };

  const insert = () => {
    if (!res) return;
    const r = onInsert(res.sequence, res.gene);
    setMsg(
      r === "changed"
        ? `retargeted the spec to ${res.gene} · ${res.length} bp`
        : r === "same"
          ? `spec already targets ${res.gene}`
          : "no target block found — add `target: gene(SYM) { }` to the spec first"
    );
  };

  return (
    <div className="ai-panel">
      <div className="ai-head">
        <span className="section-label">Gene database</span>
      </div>
      <div className="ai-row">
        <input
          className="ai-input"
          aria-label="Gene symbol"
          placeholder="Gene symbol — e.g. TP53"
          value={gene}
          onChange={(e) => setGene(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          aria-label="Sequence provider"
          style={{ flex: "none" }}
        >
          <option value="ensembl">Ensembl</option>
          <option value="ncbi">NCBI</option>
          <option value="fallback">Fallback</option>
        </select>
        <button className="btn" onClick={run} disabled={busy}>
          {busy ? "…" : "Resolve"}
        </button>
      </div>
      {err && <div className="note" role="alert">{err}</div>}
      {res && (
        <div className="resolve-out">
          <div className="hint">{res.source}</div>
          <code className="gd-seq">
            {res.sequence.slice(0, 60)}
            {res.sequence.length > 60 ? "…" : ""}
          </code>
          <div className="ai-row2">
            <span className="hint">{res.length} bp resolved live</span>
            <span className="grow" style={{ flex: 1 }} />
            <button className="btn" onClick={insert}>
              Insert into spec →
            </button>
          </div>
          {msg && <div className={"hint" + (msg.startsWith("no target") ? " ins-warn" : " ins-ok")}>{msg}</div>}
        </div>
      )}
    </div>
  );
}
