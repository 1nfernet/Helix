import { useLayoutEffect, useRef, useState } from "react";

export interface SegOption<T extends string> {
  value: T;
  label: string;
  hidden?: boolean; // e.g. the Helix view only exists when there's a sequence
}

/**
 * A segmented control with a single thumb that *slides* between options instead of
 * the active background hard-cutting from one button to the next.
 *
 * This is the one shared vocabulary for "same content, different rendering" toggles
 * (view switch, spec format, model) — a `role="group"` of `aria-pressed` buttons,
 * never a tablist (those switch content and live in <Tabs>). The thumb is measured
 * from the live active button so it adapts to variable label widths; the slide is a
 * plain transform transition, so the global reduced-motion rule collapses it to an
 * instant move with no extra code here.
 */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
  size,
}: {
  value: T;
  onChange: (v: T) => void;
  options: SegOption<T>[];
  ariaLabel: string;
  size?: "small";
}) {
  const visible = options.filter((o) => !o.hidden);
  const ref = useRef<HTMLDivElement>(null);
  const [thumb, setThumb] = useState<{ x: number; w: number } | null>(null);

  useLayoutEffect(() => {
    const root = ref.current;
    if (!root) return;
    const measure = () => {
      const active = root.querySelector<HTMLButtonElement>('button[aria-pressed="true"]');
      setThumb(active ? { x: active.offsetLeft, w: active.offsetWidth } : null);
    };
    measure();
    // Re-measure when the control resizes (font load, container reflow, options change).
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    return () => ro.disconnect();
  }, [value, visible.length]);

  return (
    <div ref={ref} className={"seg" + (size === "small" ? " small" : "")} role="group" aria-label={ariaLabel}>
      {thumb && (
        <span
          className="seg-thumb"
          aria-hidden="true"
          style={{ transform: `translateX(${thumb.x}px)`, width: thumb.w }}
        />
      )}
      {visible.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          className={value === o.value ? "active" : ""}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
