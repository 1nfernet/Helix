import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { BASE_INT, SCENE, type Base } from "../palette";
import { onReducedMotionChange, prefersReducedMotion } from "../motion";

export interface PickMods {
  shift: boolean; // cycle the alt base (prime editing)
  sweep: boolean; // live drag step — update text only, commit on release
}

interface Props {
  sequence: string;
  highlight?: { start: number; end: number }; // 0-based [start, end)
  marker?: number; // 0-based base index for the cut/edit site
  editable?: (index: number) => boolean; // which bases accept a pick (e.g. C for CBE)
  marks?: number[]; // pickable positions to pre-highlight (base-edit targets)
  onPickBase?: (index: number, mods: PickMods) => void;
}

const MAX_BASES = 64; // keep the helix legible; center the slice on the site
const RISE = 0.44;
const TWIST = (34.3 * Math.PI) / 180;
const RADIUS = 1.75;

const baseColor = (b: string) => BASE_INT[(b as Base) in BASE_INT ? (b as Base) : "N"];

/** The slice of the sequence the scene draws: MAX_BASES centred on the edit site.
 *  Render and the scene both need it — render to describe the viewport to a
 *  screen reader, the effect to build it — so it is derived in one place. */
function windowOf(sequence: string, marker?: number, highlight?: { start: number; end: number }) {
  const seq = sequence.toUpperCase().replace(/[^ACGTN]/g, "");
  const focus = marker ?? (highlight ? (highlight.start + highlight.end) / 2 : seq.length / 2);
  const half = Math.floor(MAX_BASES / 2);
  const lo = Math.max(0, Math.min(seq.length - Math.min(MAX_BASES, seq.length), Math.floor(focus) - half));
  const hi = Math.min(seq.length, lo + MAX_BASES);
  return { seq, lo, hi };
}

function rung(a: THREE.Vector3, b: THREE.Vector3, color: number, radius: number, opacity: number) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const geo = new THREE.CylinderGeometry(radius, radius, dir.length(), 10);
  const mat = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.5,
    metalness: 0.05,
    transparent: opacity < 1,
    opacity,
    emissive: opacity === 1 ? color : 0x000000,
    emissiveIntensity: opacity === 1 ? 0.15 : 0,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.addVectors(a, b).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
  return mesh;
}

export function DnaHelix({ sequence, highlight, marker, editable, marks, onPickBase }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const liveRef = useRef<HTMLSpanElement>(null);
  // Keep the latest callbacks without rebuilding the scene each render.
  const pickRef = useRef<Props["onPickBase"]>(onPickBase);
  const editableRef = useRef<Props["editable"]>(editable);
  pickRef.current = onPickBase;
  editableRef.current = editable;

  useEffect(() => {
    const container = ref.current;
    if (!container) return;
    const { seq, lo, hi } = windowOf(sequence, marker, highlight);
    if (seq.length < 2) return;
    const n = hi - lo;

    const scene = new THREE.Scene();
    // Cool fog matching the viewer backdrop (surface-2) so distant strands fade
    // into the same instrument stage the rest of the app lives on.
    scene.fog = new THREE.Fog(SCENE.fog, 22, 52);
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.85));
    const key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(6, 10, 8);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xdfe6f4, 0.35);
    fill.position.set(-6, -4, -6);
    scene.add(fill);

    const group = new THREE.Group();
    const strandA: THREE.Vector3[] = [];
    const strandB: THREE.Vector3[] = [];
    const picks: THREE.Mesh[] = [];
    const markSet = new Set(marks ?? []);
    const inHi = (i: number) => highlight != null && i >= highlight.start && i < highlight.end;

    for (let k = 0; k < n; k++) {
      const i = lo + k;
      const angle = k * TWIST;
      const a = new THREE.Vector3(RADIUS * Math.cos(angle), k * RISE, RADIUS * Math.sin(angle));
      const b = new THREE.Vector3(RADIUS * Math.cos(angle + Math.PI), k * RISE, RADIUS * Math.sin(angle + Math.PI));
      strandA.push(a);
      strandB.push(b);
      const hot = inHi(i);
      const base = seq[i] ?? "N";
      group.add(rung(a, b, baseColor(base), hot ? 0.13 : 0.07, hot ? 1 : 0.32));

      // Invisible, fat hit target spanning the whole visible base bar (raycast
      // against these), so a click anywhere on a base registers — not only on the
      // helix centreline. `mid` is the bar's midpoint (used to place the hover ring).
      const dir = new THREE.Vector3().subVectors(b, a);
      const pick = new THREE.Mesh(
        new THREE.CylinderGeometry(0.32, 0.32, dir.length(), 6, 1, true),
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
      );
      pick.position.copy(a).add(b).multiplyScalar(0.5);
      pick.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
      pick.userData.baseIndex = i;
      picks.push(pick);
      group.add(pick);

      // Glowing dot on a pre-highlighted, pickable base (base-edit targets).
      if (markSet.has(i)) {
        const dot = new THREE.Mesh(
          new THREE.SphereGeometry(0.18, 10, 10),
          new THREE.MeshStandardMaterial({ color: SCENE.accentHover, emissive: SCENE.accentHover, emissiveIntensity: 0.85 })
        );
        dot.position.copy(a);
        group.add(dot);
      }

      if (marker != null && i === marker) {
        const ring = new THREE.Mesh(
          new THREE.TorusGeometry(RADIUS + 0.5, 0.09, 10, 40),
          new THREE.MeshStandardMaterial({ color: SCENE.accent, emissive: SCENE.accent, emissiveIntensity: 0.5 })
        );
        ring.position.y = k * RISE;
        ring.rotation.x = Math.PI / 2;
        group.add(ring);
      }
    }

    for (const pts of [strandA, strandB]) {
      const curve = new THREE.CatmullRomCurve3(pts);
      const tube = new THREE.TubeGeometry(curve, n * 4, 0.2, 8, false);
      group.add(new THREE.Mesh(tube, new THREE.MeshStandardMaterial({ color: SCENE.backbone, roughness: 0.6 })));
    }

    // Reusable hover / drag indicator: a bright ring that snaps to the base under the cursor.
    const hover = new THREE.Mesh(
      new THREE.TorusGeometry(RADIUS + 0.85, 0.055, 8, 40),
      new THREE.MeshStandardMaterial({ color: SCENE.accentHover, emissive: SCENE.accentHover, emissiveIntensity: 0.7 })
    );
    hover.rotation.x = Math.PI / 2;
    hover.visible = false;
    group.add(hover);

    group.position.y = -((n - 1) * RISE) / 2;
    scene.add(group);

    const dist = Math.max(16, n * RISE * 1.15);
    camera.position.set(0, 0, dist);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.autoRotateSpeed = 1.1;
    controls.minDistance = 8;
    controls.maxDistance = 80;

    // The ambient spin is decoration, so it is the first thing to go when the
    // user asks for reduced motion — CSS can't reach this rAF loop (see the note
    // in styles.css). Dragging and picking stay fully available either way.
    let reduced = prefersReducedMotion();
    const stopReducedWatch = onReducedMotionChange((r) => {
      reduced = r;
      syncSpin();
    });

    // --- picking: click, shift-click, and drag-to-sweep -----------------
    const raycaster = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    const pickAt = (clientX: number, clientY: number): THREE.Intersection | null => {
      const rect = renderer.domElement.getBoundingClientRect();
      ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
      ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(ndc, camera);
      return raycaster.intersectObjects(picks, false)[0] ?? null;
    };
    const showHover = (y: number, editableHit: boolean) => {
      hover.position.y = y;
      (hover.material as THREE.MeshStandardMaterial).color.setHex(editableHit ? SCENE.accentHover : SCENE.inert);
      hover.visible = true;
    };

    let picking = false;
    let moved = false;
    let downShift = false;
    let hovering = false;
    let focused = false; // keyboard focus is in the viewport
    let lastIdx = -1;

    const isEditable = (idx: number) => !editableRef.current || editableRef.current(idx);
    // Stop the ambient spin while the cursor is over a pickable helix, so a base
    // isn't a moving target; keep spinning otherwise. Reduced motion and keyboard
    // focus both pin it still for the same reason: you can't aim at a moving target.
    function syncSpin() {
      controls.autoRotate = !reduced && !focused && !(!!pickRef.current && (hovering || picking));
    }

    const onDown = (e: PointerEvent) => {
      if (!pickRef.current) return;
      const hit = pickAt(e.clientX, e.clientY);
      if (!hit) return; // pressed empty space -> let OrbitControls rotate
      picking = true;
      moved = false;
      downShift = e.shiftKey;
      lastIdx = hit.object.userData.baseIndex as number;
      controls.enabled = false;
      syncSpin();
      showHover(hit.object.position.y, isEditable(lastIdx));
      try {
        renderer.domElement.setPointerCapture?.(e.pointerId);
      } catch {
        /* capture is best-effort (e.g. synthetic events) */
      }
    };
    const onMove = (e: PointerEvent) => {
      if (!pickRef.current) return;
      if (!hovering) {
        hovering = true;
        syncSpin();
      }
      const hit = pickAt(e.clientX, e.clientY);
      if (picking) {
        if (!hit) return;
        const idx = hit.object.userData.baseIndex as number;
        showHover(hit.object.position.y, isEditable(idx));
        if (idx !== lastIdx) {
          lastIdx = idx;
          moved = true;
          if (isEditable(idx)) pickRef.current(idx, { shift: false, sweep: true }); // live text only
        }
      } else if (hit) {
        showHover(hit.object.position.y, isEditable(hit.object.userData.baseIndex as number));
      } else {
        hover.visible = false;
      }
    };
    const onUp = () => {
      if (!picking) return;
      picking = false;
      controls.enabled = true;
      syncSpin();
      hover.visible = false;
      if (isEditable(lastIdx)) pickRef.current?.(lastIdx, { shift: !moved && downShift, sweep: false }); // commit
    };
    const onLeave = () => {
      hovering = false;
      syncSpin();
      if (!picking) hover.visible = false;
    };
    const el = renderer.domElement;
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointerleave", onLeave);

    // --- keyboard: the same reach as the mouse -------------------------
    // Everything the pointer can do here (aim at a base, place an edit, cycle the
    // alt base, turn the model) has a key. Without this the 3D → spec round-trip
    // — a headline feature — is mouse-only.
    const say = (msg: string) => {
      if (liveRef.current) liveRef.current.textContent = msg;
    };
    /** Move the cursor to `idx`, park the hover ring on it, and announce it. */
    const goTo = (idx: number) => {
      const target = picks.find((p) => p.userData.baseIndex === idx);
      if (!target) return;
      lastIdx = idx;
      const ok = isEditable(idx);
      showHover(target.position.y, ok);
      say(`Base ${idx + 1}, ${seq[idx] ?? "N"}${ok ? "" : ", not editable"}`);
    };
    /** Next index in `dir` that accepts an edit, so tabbing never dead-ends on
     *  a base the compiler would reject. Falls back to plain stepping. */
    const step = (from: number, dir: 1 | -1) => {
      for (let i = from + dir; i >= lo && i < hi; i += dir) if (isEditable(i)) return i;
      return from;
    };
    const orbit = (dTheta: number) => {
      const off = camera.position.clone().sub(controls.target);
      const sph = new THREE.Spherical().setFromVector3(off);
      sph.theta += dTheta;
      camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(sph));
      camera.lookAt(controls.target);
      controls.update();
    };
    const onKeyDown = (e: KeyboardEvent) => {
      const pickable = !!pickRef.current;
      // Arrows drive the base cursor when there are bases to pick; otherwise
      // they turn the model, which is the only thing left to do.
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        const dir = e.key === "ArrowRight" ? 1 : -1;
        if (!pickable) return (e.preventDefault(), orbit(dir * 0.18));
        goTo(lastIdx < lo || lastIdx >= hi ? (marker ?? lo) : step(lastIdx, dir));
        return e.preventDefault();
      }
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        return (e.preventDefault(), orbit(e.key === "ArrowUp" ? -0.18 : 0.18));
      }
      if (!pickable) return;
      if (e.key === "Home" || e.key === "End") {
        const from = e.key === "Home" ? lo - 1 : hi;
        goTo(step(from, e.key === "Home" ? 1 : -1));
        return e.preventDefault();
      }
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (lastIdx < lo || lastIdx >= hi) return goTo(marker ?? lo);
        if (!isEditable(lastIdx)) return say(`Base ${lastIdx + 1} can't be edited here`);
        // Shift mirrors shift-click: cycle the alternate base rather than place one.
        pickRef.current?.(lastIdx, { shift: e.shiftKey, sweep: false });
        say(`Edit placed at base ${lastIdx + 1}`);
      }
    };
    const onFocus = () => {
      focused = true;
      syncSpin();
      if (pickRef.current && lastIdx < lo) goTo(marker ?? lo);
    };
    const onBlur = () => {
      focused = false;
      hover.visible = false;
      syncSpin();
    };
    container.addEventListener("keydown", onKeyDown);
    container.addEventListener("focus", onFocus);
    container.addEventListener("blur", onBlur);

    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    const resize = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    syncSpin(); // sets the initial autoRotate, honouring reduced motion from the start
    animate();
    const ro = new ResizeObserver(resize);
    ro.observe(container);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      stopReducedWatch();
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointerleave", onLeave);
      container.removeEventListener("keydown", onKeyDown);
      container.removeEventListener("focus", onFocus);
      container.removeEventListener("blur", onBlur);
      controls.dispose();
      scene.traverse((o: THREE.Object3D) => {
        if (o instanceof THREE.Mesh) {
          o.geometry.dispose();
          (o.material as THREE.Material).dispose();
        }
      });
      renderer.dispose();
      if (el.parentNode === container) container.removeChild(el);
    };
    // Depend on primitives, not the `highlight` object — a fresh object each render
    // would rebuild the scene mid-sweep (killing the drag) even when nothing changed.
    // `marks` is memoized upstream, so it only changes when the guide set does.
  }, [sequence, highlight?.start, highlight?.end, marker, marks]);

  const { seq, lo, hi } = windowOf(sequence, marker, highlight);
  const keys = onPickBase
    ? "Left and right arrows move the base cursor; Enter places an edit; Shift+Enter cycles the alternate base; Home and End jump to the first and last editable base; up and down arrows turn the model."
    : "Arrow keys turn the model.";

  return (
    // role=application on the pickable helix so assistive tech passes the arrow
    // keys through to the base cursor instead of eating them for its own reading
    // mode; a read-only helix is just a focusable group you can turn.
    <div
      ref={ref}
      className={"helix-wrap" + (onPickBase ? " pickable" : "")}
      tabIndex={0}
      role={onPickBase ? "application" : "group"}
      aria-label={
        `Interactive 3D DNA helix${marker != null ? `, edit site at base ${marker + 1}` : ""}. ` +
        `Showing bases ${lo + 1} to ${hi} of ${seq.length}. ${keys}`
      }
    >
      {/* The scene encodes base identity as colour, which no screen reader can
          see — so the window it draws is also published as text. */}
      <span className="sr-only">Sequence shown: {seq.slice(lo, hi)}</span>
      <span ref={liveRef} className="sr-only" aria-live="polite" />
    </div>
  );
}
