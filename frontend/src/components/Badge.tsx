import type { ReactNode } from "react";

type BadgeKind = "ok" | "warn" | "danger" | "neutral";

export function Badge({ kind, children }: { kind: BadgeKind; children: ReactNode }) {
  return (
    <span className={`badge ${kind}`}>
      <span className="dot-i" aria-hidden="true" />
      {children}
    </span>
  );
}

/** The "the compiler chose this one" marker for a result-table row.
 *
 * Which rows the compiler picked (or which passed the constraints) is the answer
 * these tables exist to give, and a row tint is the only thing that used to say
 * it — invisible to a screen reader and easy to miss besides. */
export function PassMark({ label }: { label: string }) {
  return (
    <span className="row-sel" title={label}>
      <span aria-hidden="true">✓</span>
      <span className="sr-only">{label}</span>
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
