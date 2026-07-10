import type { PrimeEditCandidate } from "../types";
import { Metric } from "./Badge";
import { ConsequenceBadge } from "./GuideTable";

const MAX_ROWS = 12;

export function PrimeTable({ pegs }: { pegs: PrimeEditCandidate[] }) {
  const rows = [...pegs].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99)).slice(0, MAX_ROWS);
  return (
    <table className="data">
      <thead>
        <tr>
          <th className="rank">#</th>
          <th>spacer</th>
          <th>str</th>
          <th>edit</th>
          <th>PBS</th>
          <th>RTT</th>
          <th>PE3</th>
          <th>eff.</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p) => (
          <tr key={p.rank ?? p.spacer} className={p.passed ? "selected" : ""}>
            <td className="rank">{p.rank}</td>
            <td className="seq">{p.spacer}</td>
            <td className="num">{p.strand}</td>
            <td>
              {p.edit}
              {p.consequence && <ConsequenceBadge c={p.consequence} />}
            </td>
            <td className="seq">{p.pbs}</td>
            <td className="seq">{p.rtt}</td>
            <td className="num">{p.pe3_nick_position != null ? `@${p.pe3_nick_position}` : "—"}</td>
            <td><Metric value={p.predicted_efficiency} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
