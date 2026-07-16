/** Reduced-motion support for the WebGL viewers.
 *
 * The `@media (prefers-reduced-motion: reduce)` block in styles.css collapses
 * every CSS animation and transition, but it cannot reach the viewers: their
 * auto-rotate runs inside a requestAnimationFrame loop that CSS never sees. So
 * DnaHelix and ComplexViewer ask here instead. PRODUCT.md makes reduced motion
 * non-negotiable and names the 3D viewers specifically — a user who asks the OS
 * for stillness must not get a perpetually spinning molecule.
 */

const QUERY = "(prefers-reduced-motion: reduce)";

const mq = (): MediaQueryList | null =>
  typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(QUERY) : null;

/** True when the user has asked the OS to reduce motion. */
export function prefersReducedMotion(): boolean {
  return mq()?.matches ?? false;
}

/** Subscribe to changes in the preference; returns an unsubscribe function.
 *  The setting can flip while the app is open, so viewers honour it live. */
export function onReducedMotionChange(fn: (reduced: boolean) => void): () => void {
  const m = mq();
  if (!m) return () => {};
  const handler = (e: MediaQueryListEvent) => fn(e.matches);
  m.addEventListener("change", handler);
  return () => m.removeEventListener("change", handler);
}
