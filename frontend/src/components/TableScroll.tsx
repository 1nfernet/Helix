import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Horizontal scroll container for dense data tables, with edge fades that appear
 * *only* when there is more table in that direction.
 *
 * A ranked guide table is eight columns of real data and does not fit beside the
 * spec editor on a laptop — so it scrolls. Apple §12: signal that with a soft edge,
 * not a hard clip. The fades are gated on actual scroll position, so a table that
 * fits keeps its last column perfectly crisp; one that overflows gets a "there's
 * more →" cue instead of a column that looks cut off.
 */
export function TableScroll({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [edge, setEdge] = useState({ l: false, r: false });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => {
      const max = el.scrollWidth - el.clientWidth;
      setEdge({ l: el.scrollLeft > 1, r: el.scrollLeft < max - 1 });
    };
    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, [children]);

  return (
    <div className="table-scroll-wrap" data-l={edge.l || undefined} data-r={edge.r || undefined}>
      <div className="table-scroll" ref={ref}>
        {children}
      </div>
    </div>
  );
}
