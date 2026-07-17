import { TableScroll } from "./TableScroll";
import type { BatchItemResult } from "../types";

interface Props {
  results: BatchItemResult[];
  loading: boolean;
  onOpen: (r: BatchItemResult) => void;
}

function count(d: NonNullable<BatchItemResult["design"]>): number {
  return d.modality === "prime_edit" ? d.prime_edits.filter((p) => p.passed).length : d.selected.length;
}

export function BatchResults({ results, loading, onOpen }: Props) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Batch results</h3>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="empty">
            <span className="spinner" aria-hidden="true" />
            <div style={{ marginTop: 12 }}>Compiling batch…</div>
          </div>
        ) : !results.length ? (
          <div className="empty">
            <div className="big">No batch yet</div>
            Select specs on the left and press Compile.
          </div>
        ) : (
          <TableScroll>
            <table className="data">
              <thead>
                <tr>
                  <th>spec</th>
                  <th>modality</th>
                  <th>feasible</th>
                  <th>guides</th>
                  <th>delivery</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) =>
                  r.error || !r.design ? (
                    <tr key={i}>
                      <td>{r.name ?? "—"}</td>
                      <td colSpan={4} className="warn-text">error: {r.error}</td>
                      <td />
                    </tr>
                  ) : (
                    <tr key={i}>
                      <td>{r.design.spec_name}</td>
                      <td>{r.design.modality}</td>
                      <td>
                        <span className={"badge " + (r.design.feasible ? "ok" : "warn")}>
                          <span className="dot-i" />
                          {r.design.feasible ? "yes" : "no"}
                        </span>
                      </td>
                      <td className="num">{count(r.design)}</td>
                      <td>{r.design.delivery?.recommended ?? "—"}</td>
                      <td>
                        <button className="linkbtn" onClick={() => onOpen(r)}>
                          open
                        </button>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </TableScroll>
        )}
      </div>
    </section>
  );
}
