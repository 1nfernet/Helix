import { Fragment, useState } from "react";
import type { GuideCandidate, ProteinConsequence } from "../types";
import { Metric } from "./Badge";

const MAX_ROWS = 15;

const CONS_CLASS: Record<string, string> = {
  synonymous: "syn",
  missense: "mis",
  nonsense: "stop",
  "stop-loss": "stop",
  frameshift: "frame",
  "in-frame-indel": "indel",
};

export function ConsequenceBadge({ c }: { c: ProteinConsequence }) {
  const cls = CONS_CLASS[c.kind] ?? "mis";
  const title = [c.codon_change && `${c.codon_change}`, c.note].filter(Boolean).join(" · ");
  return (
    <span className={"cons " + cls} title={title || undefined}>
      {c.label}
    </span>
  );
}

function outcomeCell(g: GuideCandidate, modality: string) {
  if (modality === "base_edit" && g.base_edit) {
    const be = g.base_edit;
    return (
      <span className="seq">
        {be.window}→{be.edited_product}
        {be.bystander_count > 0 ? ` (+${be.bystander_count})` : ""}
        {be.consequence && <ConsequenceBadge c={be.consequence} />}
      </span>
    );
  }
  if (modality === "hdr" && g.hdr)
    return (
      <span className="num">
        {g.hdr.cut_to_edit_distance} bp
        {g.hdr.consequence && <ConsequenceBadge c={g.hdr.consequence} />}
      </span>
    );
  if (g.regulation)
    return (
      <span className="num">
        {g.regulation.tss_offset > 0 ? "+" : ""}
        {g.regulation.tss_offset} bp
      </span>
    );
  if (modality === "deletion") return <span className="num">@ {g.cut_site}</span>;
  if (g.repair) return <span className="num">{g.repair.frameshift_fraction.toFixed(2)}</span>;
  return <span className="hint">—</span>;
}

function GuideDetail({ g, sequence }: { g: GuideCandidate; sequence?: string }) {
  const L = g.spacer.length;
  const s = g.window_offset;
  const e = s + L;
  const seq = sequence ?? "";
  const flank5 = seq.slice(Math.max(0, s - 8), s);
  const foot = seq.slice(s, e);
  const flank3 = seq.slice(e, e + 8);
  const sites = g.off_target.sites ?? [];

  return (
    <div className="guide-detail">
      <div className="gd-block">
        <span className="gd-label">guide 5′→3′</span>
        <code className="gd-seq">
          {g.spacer}
          <span className="pam">{g.pam}</span>
        </code>
        <span className="hint">
          {g.strand === "+" ? "plus" : "minus"} strand · GC {(g.gc_content * 100).toFixed(0)}% · hairpin{" "}
          {g.self_complementarity} · cut @ {g.cut_site}
        </span>
      </div>
      {(() => {
        const cons = g.base_edit?.consequence ?? g.hdr?.consequence ?? null;
        const spb = g.hdr?.silent_pam_block ?? null;
        if (!cons && spb === null) return null;
        return (
          <div className="gd-block">
            <span className="gd-label">protein consequence</span>
            <div className="gd-checks">
              {cons && <ConsequenceBadge c={cons} />}
              {g.hdr && spb === true && <span className="cons syn">PAM-block: synonymous ✓</span>}
              {g.hdr && spb === false && <span className="cons mis">PAM-block: non-synonymous — review</span>}
            </div>
            {cons?.note && <span className="hint">{cons.note}</span>}
          </div>
        );
      })()}
      {g.checks && g.checks.length > 0 && (
        <div className="gd-block">
          <span className="gd-label">constraint checks</span>
          <div className="gd-checks">
            {g.checks.map((c) => (
              <span key={c.name} className={"gd-check " + (c.passed ? "ok" : "bad")} title={c.detail}>
                {c.passed ? "✓" : "✕"} {c.name.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}
      {g.variant_hits && g.variant_hits.length > 0 && (
        <div className="gd-block">
          <span className="gd-label">population variants — seed/PAM abolish binding in carriers</span>
          <div className="gd-checks">
            {g.variant_hits.slice(0, 10).map((v) => (
              <span
                key={v.id + ":" + v.window_pos}
                className={"gd-var" + (v.region === "seed" || v.region === "PAM" ? " risk" : "")}
                title={v.alleles}
              >
                {v.region} · {v.id}
                {v.frequency != null ? ` · ${(v.frequency * 100).toFixed(1)}%` : ""}
              </span>
            ))}
            {g.variant_hits.length > 10 && <span className="hint">+{g.variant_hits.length - 10} more</span>}
          </div>
        </div>
      )}
      {seq && (
        <div className="gd-block">
          <span className="gd-label">genomic context</span>
          <code className="gd-seq">
            <span className="arm">{flank5}</span>
            <span className="foot">{foot}</span>
            <span className="arm">{flank3}</span>
          </code>
          <span className="hint">binding footprint highlighted (plus-strand coordinates)</span>
        </div>
      )}
      <div className="gd-block">
        <span className="gd-label">off-targets · scorer {g.off_target.scorer}</span>
        {sites.length ? (
          <table className="gd-off">
            <thead>
              <tr>
                <th>site (5′→3′)</th>
                <th>mism.</th>
                <th>CFD</th>
                <th>locus</th>
              </tr>
            </thead>
            <tbody>
              {sites.slice(0, 6).map((o, i) => (
                <tr key={i}>
                  <td className="seq">{o.sequence}</td>
                  <td className="num">{o.mismatches}</td>
                  <td className="num">{o.cfd.toFixed(3)}</td>
                  <td className="hint">{o.locus ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <span className="hint">
            No off-target sites reported (max CFD {g.off_target.max_cfd.toFixed(3)}).
          </span>
        )}
      </div>
    </div>
  );
}

export function GuideTable({
  guides,
  selectedRanks,
  modality,
  sequence,
}: {
  guides: GuideCandidate[];
  selectedRanks: Set<number>;
  modality: string;
  sequence?: string;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const rows = [...guides].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99)).slice(0, MAX_ROWS);
  const outcomeHead =
    modality === "base_edit"
      ? "edit (window)"
      : modality === "hdr"
        ? "cut→edit"
        : modality === "deletion"
          ? "cut site"
          : modality === "crispri" || modality === "crispra"
            ? "TSS offset"
            : "frameshift";

  return (
    <table className="data">
      <thead>
        <tr>
          <th className="rank">#</th>
          <th>spacer (5′→3′)</th>
          <th>PAM</th>
          <th>str</th>
          <th>on-target</th>
          <th>max CFD</th>
          <th>{outcomeHead}</th>
          <th>composite</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((g) => {
          const rank = g.rank ?? -1;
          const isOpen = open === rank;
          return (
            <Fragment key={rank}>
              <tr
                className={"guide-row" + (selectedRanks.has(rank) ? " selected" : "") + (isOpen ? " open" : "")}
                onClick={() => setOpen(isOpen ? null : rank)}
                title="Click for off-targets & sequence context"
              >
                <td className="rank">
                  <span className="row-caret">{isOpen ? "▾" : "▸"}</span>
                  {g.rank}
                </td>
                <td className="seq">{g.spacer}</td>
                <td className="seq">{g.pam}</td>
                <td className="num">{g.strand}</td>
                <td>
                  <Metric value={g.on_target_score} />
                </td>
                <td className="num">{g.off_target.max_cfd.toFixed(2)}</td>
                <td>{outcomeCell(g, modality)}</td>
                <td className="num">{g.composite_score.toFixed(3)}</td>
              </tr>
              {isOpen && (
                <tr className="detail-row">
                  <td colSpan={8}>
                    <GuideDetail g={g} sequence={sequence} />
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
