import type { GuideCandidate, PrimeEditCandidate, ResolvedDesign } from "../types";
import { ConsequenceBadge } from "./GuideTable";

const TOP_N = 6;

function byRank<T extends { rank: number | null }>(a: T, b: T) {
  return (a.rank ?? 99) - (b.rank ?? 99);
}

function guideOutcome(g: GuideCandidate) {
  if (g.base_edit?.consequence) return <ConsequenceBadge c={g.base_edit.consequence} />;
  if (g.hdr?.consequence) return <ConsequenceBadge c={g.hdr.consequence} />;
  if (g.base_edit) return <span className="seq sm">{g.base_edit.window}→{g.base_edit.edited_product}</span>;
  if (g.hdr) return <span className="num">{g.hdr.cut_to_edit_distance} bp</span>;
  if (g.regulation) return <span className="num">{g.regulation.tss_offset > 0 ? "+" : ""}{g.regulation.tss_offset} bp</span>;
  if (g.repair) return <span className="num">{g.repair.frameshift_fraction.toFixed(2)} fs</span>;
  return <span className="hint">—</span>;
}

function GuideCol({ d }: { d: ResolvedDesign }) {
  if (d.modality === "prime_edit") {
    const rows = [...d.prime_edits].sort(byRank).slice(0, TOP_N);
    return (
      <table className="data cmp-guides-t">
        <thead>
          <tr>
            <th className="rank">#</th>
            <th>spacer</th>
            <th>str</th>
            <th>edit</th>
            <th>eff.</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p: PrimeEditCandidate) => (
            <tr key={p.rank ?? p.spacer} className={p.passed ? "selected" : ""}>
              <td className="rank">{p.rank ?? "—"}</td>
              <td className="seq sm">{p.spacer}</td>
              <td className="num">{p.strand}</td>
              <td className="sm">
                {p.edit}
                {p.consequence && <ConsequenceBadge c={p.consequence} />}
              </td>
              <td className="num">{p.predicted_efficiency.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  // Top-N ranked candidates (not just the passed ones) so both columns are
  // comparable in depth; passed guides stay highlighted via the `selected` class.
  const rows = [...d.guides].sort(byRank).slice(0, TOP_N);
  return (
    <table className="data cmp-guides-t">
      <thead>
        <tr>
          <th className="rank">#</th>
          <th>spacer</th>
          <th>str</th>
          <th>GC</th>
          <th>on</th>
          <th>CFD</th>
          <th>outcome</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((g: GuideCandidate) => (
          <tr key={g.rank ?? g.spacer} className={g.passed ? "selected" : ""}>
            <td className="rank">{g.rank ?? "—"}</td>
            <td className="seq sm">{g.spacer}</td>
            <td className="num">{g.strand}</td>
            <td className="num">{(g.gc_content * 100).toFixed(0)}%</td>
            <td className="num">{g.on_target_score.toFixed(2)}</td>
            <td className="num">{g.off_target.max_cfd.toFixed(2)}</td>
            <td>{guideOutcome(g)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CompareGuides({ a, b }: { a: ResolvedDesign; b: ResolvedDesign }) {
  return (
    <div className="cmp-guides">
      <div className="cmp-guides-col">
        <div className="cmp-guides-head a">
          {a.spec_name} <span className="hint">· {a.modality}</span>
        </div>
        <GuideCol d={a} />
      </div>
      <div className="cmp-guides-col">
        <div className="cmp-guides-head b">
          {b.spec_name} <span className="hint">· {b.modality}</span>
        </div>
        <GuideCol d={b} />
      </div>
    </div>
  );
}
