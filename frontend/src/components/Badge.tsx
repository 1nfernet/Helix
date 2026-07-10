import type { ReactNode } from "react";

type BadgeKind = "ok" | "warn" | "danger" | "neutral";

export function Badge({ kind, children }: { kind: BadgeKind; children: ReactNode }) {
  return (
    <span className={`badge ${kind}`}>
      <span className="dot-i" />
      {children}
    </span>
  );
}

/** A numeric score (0..max) shown as value + strength meter. */
export function Metric({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <span className="cell-metric">
      <span className="val num">{value.toFixed(2)}</span>
      <span className="meter">
        <span style={{ width: `${pct}%` }} />
      </span>
    </span>
  );
}
