import type { DeletionPlan } from "../types";

export function DeletionCard({ d }: { d: DeletionPlan }) {
  const [left, right] = d.junction.split(" / ");
  return (
    <div className="delivery">
      <div className="results-head">
        <div className="section-label">Deletion</div>
        <span className="hint">
          span {d.requested_span} · cuts {d.left_cut}‥{d.right_cut} · {d.deletion_size} bp removed
        </span>
      </div>
      <div className="donor-seq">
        <span className="arm">{left}</span>
        <span className="ins">/</span>
        <span className="arm">{right}</span>
      </div>
      <div className="note ok">
        ✓ Two cuts bracket the region; NHEJ rejoins the 5′ and 3′ ends at the junction above.
      </div>
    </div>
  );
}
