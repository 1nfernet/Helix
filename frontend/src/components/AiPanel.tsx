import { useState } from "react";
import { author, critique } from "../api";
import type { CritiqueResult, Format } from "../types";

const MODELS = [
  { id: "claude-haiku-4-5-20251001", label: "Haiku" },
  { id: "claude-sonnet-5", label: "Sonnet" },
];

export function AiPanel({
  configured,
  demo = false,
  source,
  format,
  onDraft,
  onApply,
}: {
  configured: boolean;
  demo?: boolean;
  source: string;
  format: Format;
  onDraft: (source: string, format: Format) => void;
  onApply: (source: string) => void;
}) {
  const [request, setRequest] = useState("");
  const [model, setModel] = useState(MODELS[0].id);
  const [busy, setBusy] = useState<"" | "author" | "critique">("");
  const [crit, setCrit] = useState<CritiqueResult | null>(null);
  const [err, setErr] = useState("");
  const [last, setLast] = useState<{ what: string; cost: number | null } | null>(null);

  if (!configured) {
    return (
      <div className="ai-panel">
        <div className="ai-head">
          <span className="section-label">AI assist</span>
        </div>
        <div className="hint">
          Set <code>ANTHROPIC_API_KEY</code> on the backend to enable natural-language authoring
          and design critique.
        </div>
      </div>
    );
  }

  const draft = async () => {
    if (!request.trim() || busy) return;
    setBusy("author");
    setErr("");
    setCrit(null);
    try {
      const r = await author(request, model);
      onDraft(r.source, r.format);
      setLast({ what: "draft", cost: r.cost });
    } catch (e: unknown) {
      setErr((e as { message?: string })?.message || "Authoring failed");
    } finally {
      setBusy("");
    }
  };

  const runCritique = async () => {
    if (!source.trim() || busy) return;
    setBusy("critique");
    setErr("");
    try {
      const r = await critique(source, format, model);
      setCrit(r);
      setLast({ what: "critique", cost: r.cost });
    } catch (e: unknown) {
      setErr((e as { message?: string })?.message || "Critique failed");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="ai-panel">
      <div className="ai-head">
        <span className="section-label">AI assist</span>
        {demo && <span className="ai-demo-tag" title="No ANTHROPIC_API_KEY set — replies are canned, not from a model">demo</span>}
        <div className="seg small">
          {MODELS.map((m) => (
            <button key={m.id} className={model === m.id ? "active" : ""} onClick={() => setModel(m.id)}>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="ai-row">
        <input
          className="ai-input"
          placeholder="Describe an edit — e.g. “base-edit C→T in TP53, HEK293T, avoid BsaI”"
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && draft()}
        />
        <button className="btn" onClick={draft} disabled={!!busy}>
          {busy === "author" ? "Drafting…" : "Draft"}
        </button>
      </div>

      <div className="ai-row2">
        <button className="linkbtn" onClick={runCritique} disabled={!!busy}>
          {busy === "critique" ? "Reviewing…" : "Critique current spec"}
        </button>
        {last && last.cost != null && (
          <span className="hint">
            ~${last.cost.toFixed(4)} · {last.what}
          </span>
        )}
      </div>

      {demo && (
        <div className="hint ai-demo-note">
          Demo mode — replies are canned samples, not model output. Set <code>ANTHROPIC_API_KEY</code> on the
          backend for real drafting &amp; critique.
        </div>
      )}

      {err && <div className="note">{err}</div>}

      {crit && (
        <div className="critique">
          {crit.summary && <div className="crit-summary">{crit.summary}</div>}
          {crit.findings.map((f, i) => (
            <div key={i} className={"crit-finding " + f.severity}>
              <span className={"crit-sev " + f.severity}>{f.severity}</span>
              <div className="crit-msg">
                {f.message}
                {f.suggestion ? <span className="crit-sug"> — {f.suggestion}</span> : null}
              </div>
            </div>
          ))}
          {!crit.findings.length && <div className="hint">No issues flagged.</div>}
          {crit.revised_source && (
            <button
              className="btn"
              onClick={() => {
                onApply(crit.revised_source!);
                setCrit(null);
              }}
            >
              Apply {Object.keys(crit.suggested_constraint_edits).length} suggested edit(s) &amp; recompile
            </button>
          )}
        </div>
      )}
    </div>
  );
}
