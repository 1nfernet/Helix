import { useMemo, useState } from "react";
import type { ResolvedDesign, RunSummary } from "../types";
import { CompareGuides } from "./CompareGuides";

type Slot = "a" | "b";

function summarize(d: ResolvedDesign): Record<string, string> {
  const isPrime = d.modality === "prime_edit";
  const pool: { on_target_score: number; composite_score: number }[] = isPrime
    ? d.prime_edits
    : d.selected.length
      ? d.selected
      : d.guides;
  const topOn = pool.length ? Math.max(...pool.map((g) => g.on_target_score)) : 0;
  const topComp = pool.length ? Math.max(...pool.map((g) => g.composite_score)) : 0;
  return {
    Modality: d.modality,
    Enzyme: d.resolved_enzyme,
    Feasible: d.feasible ? "yes" : "no",
    Candidates: String(isPrime ? d.prime_edits.length : d.guides.length),
    "Top on-target": topOn.toFixed(2),
    "Top composite": topComp.toFixed(3),
    Delivery: d.delivery?.recommended ?? "—",
    "Cargo (kb)": d.delivery ? String(d.delivery.cargo_kb) : "—",
    Safety: d.safety.allowed ? "allowed" : "blocked",
  };
}

const ROWS = [
  "Modality",
  "Enzyme",
  "Feasible",
  "Candidates",
  "Top on-target",
  "Top composite",
  "Delivery",
  "Cargo (kb)",
  "Safety",
];

function ago(ts: number): string {
  const s = Math.max(0, (Date.now() - ts) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function ComparePanel({
  runs,
  aId,
  bId,
  a,
  b,
  onPick,
}: {
  runs: RunSummary[];
  aId: string;
  bId: string;
  a: ResolvedDesign | null;
  b: ResolvedDesign | null;
  onPick: (slot: Slot, id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"summary" | "guides">("summary");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return runs;
    return runs.filter(
      (r) => r.name.toLowerCase().includes(q) || r.modality.toLowerCase().includes(q),
    );
  }, [runs, query]);

  if (!runs.length) {
    return (
      <div className="empty">
        <div className="big">Nothing to compare yet</div>
        Compile a couple of designs, then pick two here.
      </div>
    );
  }

  // Click-to-assign: fill A, then B; a third pick shifts B→A and takes the new slot.
  // Clicking a run already in a slot clears it.
  function assign(id: string) {
    if (id === aId) return onPick("a", "");
    if (id === bId) return onPick("b", "");
    if (!aId) return onPick("a", id);
    if (!bId) return onPick("b", id);
    onPick("a", bId);
    onPick("b", id);
  }

  const sa = a ? summarize(a) : null;
  const sb = b ? summarize(b) : null;
  const byId = (id: string) => runs.find((r) => r.id === id);

  const slotChip = (slot: Slot, id: string, name?: string) => (
    <div className={"cmp-slot " + (id ? "filled " + slot : "")}>
      <span className="cmp-slot-tag">{slot.toUpperCase()}</span>
      {id ? (
        <>
          <span className="cmp-slot-name" title={name}>
            {name ?? byId(id)?.name ?? id}
          </span>
          <button className="cmp-slot-x" title="clear" onClick={() => onPick(slot, "")}>
            ×
          </button>
        </>
      ) : (
        <span className="cmp-slot-empty">pick a run below</span>
      )}
    </div>
  );

  return (
    <div className="panel compare">
      <div className="cmp-heads">
        <div className="cmp-col">{slotChip("a", aId, a?.spec_name)}</div>
        <div className="cmp-mid">vs</div>
        <div className="cmp-col">{slotChip("b", bId, b?.spec_name)}</div>
      </div>

      {a && b && sa && sb ? (
        <>
          <div className="cmp-toggle">
            <button className={view === "summary" ? "active" : ""} onClick={() => setView("summary")}>
              Summary
            </button>
            <button className={view === "guides" ? "active" : ""} onClick={() => setView("guides")}>
              Guides
            </button>
          </div>
          {view === "summary" ? (
            <table className="cmp-table">
              <tbody>
                {ROWS.map((k) => {
                  const differ = sa[k] !== sb[k];
                  return (
                    <tr key={k} className={differ ? "differ" : ""}>
                      <td className="cmp-a">{sa[k]}</td>
                      <th className="cmp-k">{k}</th>
                      <td className="cmp-b">{sb[k]}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <CompareGuides a={a} b={b} />
          )}
        </>
      ) : (
        <div className="hint" style={{ padding: "12px 4px" }}>
          Click a run below to fill {aId ? "slot B" : "slot A"}
          {aId || bId ? " — click a picked run to remove it." : "."}
        </div>
      )}

      <div className="cmp-picker">
        <div className="cmp-picker-head">
          <input
            className="cmp-search"
            placeholder={`Filter ${runs.length} runs by name or modality…`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <span className="cmp-count">{filtered.length}</span>
        </div>
        <div className="cmp-runs">
          {filtered.map((r) => {
            const mark = r.id === aId ? "a" : r.id === bId ? "b" : "";
            return (
              <button
                key={r.id}
                className={"run-item cmp-run" + (mark ? " sel " + mark : "")}
                onClick={() => assign(r.id)}
                title={mark ? `Slot ${mark.toUpperCase()} — click to remove` : r.name}
              >
                <span className={"dot-i " + (r.feasible ? "ok" : "warn")} />
                <span className="run-name">{r.name}</span>
                <span className="run-meta">
                  {r.modality}
                  {r.delivery ? ` · ${r.delivery}` : ""} · {ago(r.ts)}
                </span>
                {mark && <span className={"cmp-run-tag " + mark}>{mark.toUpperCase()}</span>}
              </button>
            );
          })}
          {!filtered.length && <div className="hint" style={{ padding: "10px 8px" }}>No runs match “{query}”.</div>}
        </div>
      </div>
    </div>
  );
}
