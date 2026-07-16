import { useEffect, useRef, useState } from "react";
import { ColormakerRegistry, Stage } from "ngl";
import { foldDomain, getStructure } from "../api";
import { CHAIN_HEX, STAGE_BG } from "../palette";
import { onReducedMotionChange, prefersReducedMotion } from "../motion";
import type { FoldResult, ResolvedDesign, StructureInfo } from "../types";

interface Props {
  design: ResolvedDesign;
}

/** Colour the complex from CHAIN_HEX rather than NGL's stock "moleculetype"
 *  scheme, so the swatches in the legend below are the colours actually on
 *  screen — with the built-in scheme the legend was only guessing at them.
 *  Registered once at module load; the id is stable for the session. */
const CHAIN_SCHEME = ColormakerRegistry.addSelectionScheme(
  // [colour, NGL selection, per-entry params]. The trailing `undefined` is the
  // optional params slot the tuple type requires. "*" is the catch-all and must
  // stay last — entries are matched in order.
  [
    [CHAIN_HEX.protein, "protein", undefined],
    [CHAIN_HEX.rna, "rna", undefined],
    [CHAIN_HEX.dna, "dna", undefined],
    [CHAIN_HEX.other, "*", undefined],
  ],
  "helix-moleculetype"
);

const DOMAINS = [
  { id: "hnh", label: "HNH domain" },
  { id: "pi", label: "PAM-interacting" },
  { id: "bridge", label: "bridge helix" },
];

/**
 * The macromolecular complex in 3D. `helix.structure` assembles this design's own
 * Cas9-sgRNA-DNA complex; a reference Cas9 complex (PDB 4OO8) stands in for the full
 * geometry, and "Fold" runs real ESMFold structure prediction on a SpCas9 domain,
 * rendering the returned model coloured by pLDDT confidence.
 */
export function ComplexViewer({ design }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<StructureInfo | null>(null);
  const [folded, setFolded] = useState<FoldResult | null>(null);
  const [folding, setFolding] = useState(false);
  const [region, setRegion] = useState("hnh");
  const [foldErr, setFoldErr] = useState("");
  const pdbId = info?.reference_pdb ?? "4OO8";

  useEffect(() => {
    getStructure(design).then(setInfo).catch(() => setInfo(null));
  }, [design]);

  useEffect(() => {
    const mount = ref.current;
    if (!mount) return;
    let cancelled = false;
    const host = document.createElement("div");
    host.style.width = "100%";
    host.style.height = "100%";
    mount.appendChild(host);
    const stage = new Stage(host, { backgroundColor: STAGE_BG });

    const loader = folded
      ? stage.loadFile(new Blob([folded.pdb], { type: "text/plain" }), { ext: "pdb" })
      : stage.loadFile(`https://files.rcsb.org/download/${pdbId}.cif`, { ext: "cif" });

    loader
      .then((comp) => {
        if (cancelled || !comp) return;
        if (folded) {
          comp.addRepresentation("cartoon", { colorScheme: "bfactor", colorReverse: true });
        } else {
          comp.addRepresentation("cartoon", { colorScheme: CHAIN_SCHEME });
          comp.addRepresentation("base", { colorScheme: CHAIN_SCHEME });
        }
        stage.handleResize();
        comp.autoView();
        // The idle spin is decoration; a reduced-motion user gets a still model
        // they can still drag. CSS can't reach NGL's own render loop.
        stage.setSpin(!prefersReducedMotion());
      })
      .catch(() => {
        if (!cancelled) setError(folded ? "Could not render the folded model." : `Could not load ${pdbId} from RCSB.`);
      });

    const onResize = () => stage.handleResize();
    window.addEventListener("resize", onResize);
    const stopReducedWatch = onReducedMotionChange((reduced) => stage.setSpin(!reduced));
    return () => {
      cancelled = true;
      window.removeEventListener("resize", onResize);
      stopReducedWatch();
      stage.dispose();
      host.remove();
    };
  }, [pdbId, folded]);

  const doFold = async () => {
    setFolding(true);
    setFoldErr("");
    try {
      setFolded(await foldDomain(region));
    } catch (e: unknown) {
      setFoldErr((e as { message?: string })?.message || "Fold failed");
    } finally {
      setFolding(false);
    }
  };

  return (
    <>
      <div
        ref={ref}
        className="helix-wrap"
        role="img"
        aria-label={`3D view of the Cas9 complex${folded ? `, folded model of ${folded.name}` : `, reference structure ${pdbId}`}. Drag to rotate.`}
      >
        {error && <div className="viewer-msg" role="alert">{error}</div>}
      </div>
      <div className="complex-info">
        {folded ? (
          <div className="note ok">
            ✓ Folded {folded.name} · {folded.residues} aa · mean pLDDT {folded.plddt} ({folded.tool}) — coloured by
            per-residue confidence. <button className="linkbtn" onClick={() => setFolded(null)}>show reference</button>
          </div>
        ) : (
          info && (
            <>
              {info.available && info.chains && (
                <div className="chain-row">
                  {info.chains.map((c) => (
                    <span key={c.id} className="chain" title={c.sequence}>
                      <i aria-hidden="true" style={{ background: CHAIN_HEX[c.type] ?? CHAIN_HEX.other }} />
                      {c.name} · {c.length}
                      {c.type === "protein" ? " aa" : c.type === "rna" ? " nt" : " bp"}
                    </span>
                  ))}
                </div>
              )}
              <div className="hint" style={{ marginTop: 8 }}>
                {info.available
                  ? `Complex assembled for this guide; reference PDB ${pdbId} shown. Full-complex folding needs AlphaFold3/Boltz (GPU).`
                  : info.reason}
              </div>
            </>
          )
        )}
        <div className="ai-row2" style={{ marginTop: 10 }}>
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            style={{ flex: "none" }}
            aria-label="Domain to fold"
          >
            {DOMAINS.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
          <button className="btn" onClick={doFold} disabled={folding}>
            {folding ? "Folding…" : "Fold with ESMFold"}
          </button>
          <span className="hint">real structure prediction (no GPU)</span>
        </div>
        {foldErr && <div className="note" role="alert" style={{ marginTop: 8 }}>{foldErr}</div>}
      </div>
    </>
  );
}
