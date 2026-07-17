import type { HdrDonor } from "../types";

export function DonorCard({ d }: { d: HdrDonor }) {
  return (
    <div className="delivery">
      <div className="results-head">
        <div className="section-label">Donor · {d.donor_type}</div>
        <span className="hint">
          {d.edit} · cut→edit {d.cut_to_edit_distance} bp · arms {d.arm_length} nt · strand {d.strand}
        </span>
      </div>
      <div className="donor-seq">
        <span className="arm">{d.left_arm}</span>
        <span className="ins">{d.insert || "∅"}</span>
        <span className="arm">{d.right_arm}</span>
      </div>
      <div className={"note " + (d.pam_disrupted ? "ok" : "")}>
        {d.pam_disrupted ? "✓ " : ""}
        {d.recut_note}
      </div>
    </div>
  );
}
