import { lazy, Suspense, useMemo, useState } from "react";
import type { ApiError, CompileResult, ResolvedDesign } from "../types";
import type { PickMods } from "./DnaHelix";
import { Badge } from "./Badge";
import { AnalyzeCard } from "./AnalyzeCard";
import { DeletionCard } from "./DeletionCard";
import { DeliveryCard } from "./DeliveryCard";
import { DonorCard } from "./DonorCard";
import { GuideTable } from "./GuideTable";
import { OrderCard } from "./OrderCard";
import { PrimeTable } from "./PrimeTable";

// The 3D viewers pull in heavy libraries (Three.js / NGL); load each only when its tab opens.
const DnaHelix = lazy(() => import("./DnaHelix").then((m) => ({ default: m.DnaHelix })));
const ComplexViewer = lazy(() => import("./ComplexViewer").then((m) => ({ default: m.ComplexViewer })));

type View = "table" | "helix" | "complex";
type Section = "guides" | "delivery" | "order" | "analyze";

function Summary({ d }: { d: ResolvedDesign }) {
  const isPrime = d.modality === "prime_edit";
  const pool = isPrime ? d.prime_edits : d.selected.length ? d.selected : d.guides;
  const topOn = pool.length ? Math.max(...pool.map((g) => g.on_target_score)) : null;
  const count = isPrime ? d.prime_edits.length : d.selected.length || d.guides.length;
  const stats: [string, string][] = [
    [isPrime ? "pegRNAs" : "guides", String(count)],
    ...(topOn != null ? ([["top on-target", topOn.toFixed(2)]] as [string, string][]) : []),
    ...(d.delivery ? ([["delivery", d.delivery.recommended]] as [string, string][]) : []),
  ];
  return (
    <>
      <div className="summary">
        <span className="title">{d.spec_name}</span>
        <Badge kind="neutral">{d.modality}</Badge>
        <Badge kind="neutral">{d.resolved_enzyme}</Badge>
        <Badge kind={d.feasible ? "ok" : "warn"}>{d.feasible ? "feasible" : "infeasible"}</Badge>
        <Badge kind={d.safety.allowed ? "ok" : "danger"}>
          {d.safety.allowed ? "safety: allowed" : "safety: blocked"}
        </Badge>
      </div>
      {d.target && (
        <div className="meta-row">
          {d.target.gene} · {d.target.genome_build} · {d.target.length} nt window · <code>{d.target.source}</code>
        </div>
      )}
      {d.safety.allowed && (
        <div className="stat-strip">
          {stats.map(([label, value]) => (
            <div key={label} className="stat">
              <span className="sv">{value}</span>
              <span className="sl">{label}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function siteFor(d: ResolvedDesign): { highlight?: { start: number; end: number }; marker?: number } {
  if (d.modality === "prime_edit" && d.prime_edits.length) {
    const p = d.prime_edits[0];
    return { highlight: { start: Math.max(0, p.nick_position - 2), end: p.nick_position + 2 }, marker: p.nick_position };
  }
  const g = d.selected[0] ?? d.guides[0];
  if (d.modality === "hdr" && g?.hdr) {
    const e = g.hdr.edit_pos;
    return { highlight: { start: Math.max(0, e - 2), end: e + 2 }, marker: e };
  }
  if (d.modality === "deletion" && d.deletion) {
    const p = d.deletion;
    return { highlight: { start: p.left_cut, end: p.right_cut }, marker: Math.round((p.left_cut + p.right_cut) / 2) };
  }
  if ((d.modality === "crispri" || d.modality === "crispra") && g?.regulation) {
    const tss = g.window_offset + 10 - g.regulation.tss_offset; // TSS = guide centre − offset
    return { highlight: { start: Math.max(0, tss - 2), end: tss + 2 }, marker: tss };
  }
  if (g) return { highlight: { start: g.window_offset, end: g.window_offset + 20 }, marker: g.cut_site };
  return {};
}

const LEGEND: [string, string][] = [
  ["A", "#4a7a53"],
  ["T", "#c96442"],
  ["G", "#3f6fb0"],
  ["C", "#c79a3a"],
];

function DesignView({
  result,
  view,
  setView,
  tab,
  setTab,
  onPickBase,
}: {
  result: CompileResult;
  view: View;
  setView: (v: View) => void;
  tab: Section;
  setTab: (t: Section) => void;
  onPickBase?: (i: number, mods: PickMods) => void;
}) {
  const d = result.design;
  const selectedRanks = new Set<number>(d.selected.map((g) => g.rank ?? -1));
  const isPrime = d.modality === "prime_edit";
  const isBase = d.modality === "base_edit";
  const isHdr = d.modality === "hdr";
  const isDeletion = d.modality === "deletion";
  const isReg = d.modality === "crispri" || d.modality === "crispra";
  const site = siteFor(d);
  const hasHelix = !!d.target?.sequence;
  const pickable = (isPrime || isBase || isHdr) && !!onPickBase;
  const donorGuide = d.selected[0] ?? d.guides[0];

  // Base editing edits one base type (C for CBE, A for ABE) and only where a guide's
  // window reaches it — restrict picks to those positions so every pick yields a result.
  const seqU = (d.target?.sequence ?? "").toUpperCase();
  const be = d.selected[0]?.base_edit ?? d.guides[0]?.base_edit;
  const beTarget = be?.editor === "ABE" ? "A" : be?.editor === "CBE" || be?.editor === "CGBE" ? "C" : null;
  const editableSet = useMemo(() => {
    if (!isBase || !beTarget) return null;
    const s = new Set<number>();
    for (const g of d.guides) {
      const b = g.base_edit;
      if (!b) continue;
      for (let i = b.window_abs_start; i < b.window_abs_start + b.window.length; i++) {
        if (seqU[i] === beTarget) s.add(i);
      }
    }
    return s;
  }, [d.guides, isBase, beTarget, seqU]);
  const editable = editableSet ? (i: number) => editableSet.has(i) : undefined;
  const editablePositions = useMemo(
    () => (editableSet ? [...editableSet].sort((a, b) => a - b) : undefined),
    [editableSet]
  );
  const hint = isBase
    ? `click a highlighted ${beTarget ?? "C/A"} (${be?.editor ?? "base editor"}'s reach) to target it · drag the background to rotate`
    : "click to place the edit · drag to sweep · shift-click to change the edited base";

  // Result tabs available for this design; keep a valid one selected.
  const availableTabs: Section[] = [
    "guides",
    ...(d.delivery ? (["delivery"] as Section[]) : []),
    ...(d.target ? (["order"] as Section[]) : []),
    ...(d.target && !isReg ? (["analyze"] as Section[]) : []),
  ];
  const activeTab = availableTabs.includes(tab) ? tab : "guides";

  return (
    <>
      <Summary d={d} />

      {!d.safety.allowed &&
        d.safety.reasons.map((r, i) => (
          <div key={i} className="error-card" style={{ marginBottom: 12 }}>
            <div className="etype">safety</div>
            <pre>{r}</pre>
          </div>
        ))}

      {d.infeasibility_notes.map((n, i) => (
        <div key={i} className="note">
          {n}
        </div>
      ))}

      {d.safety.allowed && (
        <>
          <div className="rtabs" role="tablist">
            <button className={activeTab === "guides" ? "active" : ""} onClick={() => setTab("guides")}>
              {isPrime ? "pegRNAs" : "Guides"}
            </button>
            {d.delivery && (
              <button className={activeTab === "delivery" ? "active" : ""} onClick={() => setTab("delivery")}>
                Delivery
              </button>
            )}
            {d.target && (
              <button className={activeTab === "order" ? "active" : ""} onClick={() => setTab("order")}>
                Order
              </button>
            )}
            {d.target && !isReg && (
              <button className={activeTab === "analyze" ? "active" : ""} onClick={() => setTab("analyze")}>
                Analyze
              </button>
            )}
          </div>

          {activeTab === "guides" && (
            <>
              <div className="results-head">
                <div className="section-label">
                  {isHdr
                    ? "Knock-in guides + donor"
                    : isDeletion
                      ? "Flanking guides + deletion"
                      : d.modality === "crispri"
                        ? "CRISPRi guides"
                        : d.modality === "crispra"
                          ? "CRISPRa guides"
                          : isPrime
                            ? "pegRNA candidates"
                            : "Guides"}
                </div>
                <div className="seg small">
                  <button className={view === "table" ? "active" : ""} onClick={() => setView("table")}>
                    Table
                  </button>
                  {hasHelix && (
                    <button className={view === "helix" ? "active" : ""} onClick={() => setView("helix")}>
                      Helix
                    </button>
                  )}
                  <button className={view === "complex" ? "active" : ""} onClick={() => setView("complex")}>
                    Complex
                  </button>
                </div>
              </div>

              {view === "helix" && hasHelix ? (
                <>
                  <Suspense fallback={<div className="helix-wrap" />}>
                    <DnaHelix
                      sequence={d.target!.sequence}
                      highlight={site.highlight}
                      marker={site.marker}
                      editable={editable}
                      marks={editablePositions}
                      onPickBase={pickable ? onPickBase : undefined}
                    />
                  </Suspense>
                  <div className="helix-legend">
                    {LEGEND.map(([b, c]) => (
                      <span key={b}>
                        <i style={{ background: c }} />
                        {b}
                      </span>
                    ))}
                    <span className="grow" />
                    <span className="muted">
                      {pickable ? hint : "highlighted = guide · ring = cut/edit site · drag to rotate"}
                    </span>
                  </div>
                </>
              ) : view === "complex" ? (
                <Suspense fallback={<div className="helix-wrap" />}>
                  <ComplexViewer design={d} />
                </Suspense>
              ) : isPrime ? (
                <PrimeTable pegs={d.prime_edits} />
              ) : (
                <GuideTable
                  guides={d.guides}
                  selectedRanks={selectedRanks}
                  modality={d.modality}
                  sequence={d.target?.sequence}
                />
              )}

              {isHdr && donorGuide?.hdr && <DonorCard d={donorGuide.hdr} />}
              {isDeletion && d.deletion && <DeletionCard d={d.deletion} />}
            </>
          )}

          {activeTab === "delivery" && d.delivery && <DeliveryCard d={d.delivery} />}
          {activeTab === "order" && d.target && <OrderCard design={d} />}
          {activeTab === "analyze" && d.target && !isReg && <AnalyzeCard design={d} />}
        </>
      )}

      <details className="prov">
        <summary>Provenance &amp; protocol</summary>
        <dl className="kv">
          <dt>helix</dt>
          <dd>{d.provenance.helix_version}</dd>
          <dt>build</dt>
          <dd>{d.provenance.genome_build}</dd>
          <dt>run</dt>
          <dd>{d.provenance.timestamp_utc}</dd>
          {Object.entries(d.provenance.adapters).map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        <pre className="protocol">{result.protocol}</pre>
      </details>
    </>
  );
}

export function ResultsPanel({
  result,
  error,
  loading,
  onPickBase,
}: {
  result: CompileResult | null;
  error: ApiError | null;
  loading: boolean;
  onPickBase?: (i: number, mods: PickMods) => void;
}) {
  const [view, setView] = useState<View>("table");
  const [tab, setTab] = useState<Section>("guides");
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Design</h2>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="empty">
            <span className="spinner" />
            <div style={{ marginTop: 12 }}>Compiling…</div>
          </div>
        ) : error ? (
          <div className="error-card">
            <div className="etype">{error.type} error</div>
            <pre>{error.message}</pre>
          </div>
        ) : result ? (
          <DesignView result={result} view={view} setView={setView} tab={tab} setTab={setTab} onPickBase={onPickBase} />
        ) : (
          <div className="empty">
            <div className="big">No design yet</div>
            Write or load a spec, then press Compile.
          </div>
        )}
      </div>
    </section>
  );
}
