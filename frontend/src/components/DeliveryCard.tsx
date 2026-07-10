import type { DeliveryRecommendation } from "../types";

export function DeliveryCard({ d }: { d: DeliveryRecommendation }) {
  return (
    <div className="delivery">
      <div className="results-head">
        <div className="section-label">Delivery</div>
        <span className="hint">
          cargo ~{d.cargo_kb} kb · {d.context.replace("_", " ")}
        </span>
      </div>
      <div className="delivery-rows">
        {d.options.map((o) => (
          <div key={o.method} className={"delivery-row" + (o.method === d.recommended ? " rec" : "")}>
            <div className="drow-main">
              <span className="dm">
                {o.method}
                {o.method === d.recommended && <span className="rec-tag">recommended</span>}
              </span>
              <span className="meter">
                <span style={{ width: `${Math.round(o.score * 100)}%` }} />
              </span>
              <span className="num">{o.score.toFixed(2)}</span>
            </div>
            {o.warnings.map((w, i) => (
              <div key={i} className="drow-warn">⚠ {w}</div>
            ))}
          </div>
        ))}
      </div>
      {d.notes.map((n, i) => (
        <div key={i} className="note">
          {n}
        </div>
      ))}
    </div>
  );
}
