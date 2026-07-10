import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

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

const BASE_COLOR: Record<string, number> = {
  A: 0x4a7a53,
  T: 0xc96442,
  G: 0x3f6fb0,
  C: 0xc79a3a,
  N: 0x9a968d,
};
const BACKBONE = 0xbcb2a4;
const ACCENT = 0xc96442;
const HOVER = 0xe0894f;

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
  // Keep the latest callbacks without rebuilding the scene each render.
  const pickRef = useRef<Props["onPickBase"]>(onPickBase);
  const editableRef = useRef<Props["editable"]>(editable);
  pickRef.current = onPickBase;
  editableRef.current = editable;

  useEffect(() => {
    const container = ref.current;
    if (!container) return;
    const seq = sequence.toUpperCase().replace(/[^ACGTN]/g, "");
    if (seq.length < 2) return;

    const focus = marker ?? (highlight ? (highlight.start + highlight.end) / 2 : seq.length / 2);
    const half = Math.floor(MAX_BASES / 2);
    const lo = Math.max(0, Math.min(seq.length - Math.min(MAX_BASES, seq.length), Math.floor(focus) - half));
    const hi = Math.min(seq.length, lo + MAX_BASES);
    const n = hi - lo;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xf4f1ea, 22, 52);
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.85));
    const key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(6, 10, 8);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffe9dd, 0.35);
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
      group.add(rung(a, b, BASE_COLOR[base] ?? BASE_COLOR.N, hot ? 0.13 : 0.07, hot ? 1 : 0.32));

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
          new THREE.MeshStandardMaterial({ color: HOVER, emissive: HOVER, emissiveIntensity: 0.85 })
        );
        dot.position.copy(a);
        group.add(dot);
      }

      if (marker != null && i === marker) {
        const ring = new THREE.Mesh(
          new THREE.TorusGeometry(RADIUS + 0.5, 0.09, 10, 40),
          new THREE.MeshStandardMaterial({ color: ACCENT, emissive: ACCENT, emissiveIntensity: 0.5 })
        );
        ring.position.y = k * RISE;
        ring.rotation.x = Math.PI / 2;
        group.add(ring);
      }
    }

    for (const pts of [strandA, strandB]) {
      const curve = new THREE.CatmullRomCurve3(pts);
      const tube = new THREE.TubeGeometry(curve, n * 4, 0.2, 8, false);
      group.add(new THREE.Mesh(tube, new THREE.MeshStandardMaterial({ color: BACKBONE, roughness: 0.6 })));
    }

    // Reusable hover / drag indicator: a bright ring that snaps to the base under the cursor.
    const hover = new THREE.Mesh(
      new THREE.TorusGeometry(RADIUS + 0.85, 0.055, 8, 40),
      new THREE.MeshStandardMaterial({ color: HOVER, emissive: HOVER, emissiveIntensity: 0.7 })
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
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.1;
    controls.minDistance = 8;
    controls.maxDistance = 80;

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
      (hover.material as THREE.MeshStandardMaterial).color.setHex(editableHit ? HOVER : 0x9a968d);
      hover.visible = true;
    };

    let picking = false;
    let moved = false;
    let downShift = false;
    let hovering = false;
    let lastIdx = -1;

    const isEditable = (idx: number) => !editableRef.current || editableRef.current(idx);
    // Stop the ambient spin while the cursor is over a pickable helix, so a base
    // isn't a moving target; keep spinning otherwise.
    const syncSpin = () => {
      controls.autoRotate = !(!!pickRef.current && (hovering || picking));
    };

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
    animate();
    const ro = new ResizeObserver(resize);
    ro.observe(container);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointerleave", onLeave);
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

  return <div ref={ref} className={"helix-wrap" + (onPickBase ? " pickable" : "")} />;
}
