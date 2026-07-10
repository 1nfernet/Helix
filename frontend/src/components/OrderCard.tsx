import { useEffect, useState } from "react";
import { exportOligos } from "../api";
import type { ExportResult, ResolvedDesign } from "../types";

export function OrderCard({ design }: { design: ResolvedDesign }) {
  const [data, setData] = useState<ExportResult | null>(null);

  useEffect(() => {
    exportOligos(design).then(setData).catch(() => setData(null));
  }, [design]);

  if (!data || !data.items.length) return null;

  const download = () => {
    const blob = new Blob([data.csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${design.spec_name || "design"}_oligos.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="delivery">
      <div className="results-head">
        <div className="section-label">Order-ready oligos</div>
        <span className="hint">
          ~${data.cost.total_usd} · {data.cost.total_bases} nt · {data.cost.item_count} oligos
        </span>
      </div>
      <table className="data order-table">
        <thead>
          <tr>
            <th>name</th>
            <th>kind</th>
            <th>sequence (5′→3′)</th>
            <th>nt</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((it) => (
            <tr key={it.name} title={it.note}>
              <td className="seq">{it.name}</td>
              <td className="hint">{it.kind}</td>
              <td className="seq order-seq">{it.sequence}</td>
              <td className="num">{it.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="btn" onClick={download}>
        Download CSV
      </button>
    </div>
  );
}
