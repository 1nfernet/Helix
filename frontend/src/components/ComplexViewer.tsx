import { useEffect, useRef, useState } from "react";
import { Stage } from "ngl";
import { foldDomain, getStructure } from "../api";
import type { FoldResult, ResolvedDesign, StructureInfo } from "../types";

interface Props {
  design: ResolvedDesign;
}

const CHAIN_COLOR: Record<string, string> = { protein: "#3f6fb0", rna: "#c96442", dna: "#4a7a53" };
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
    const stage = new Stage(host, { backgroundColor: "#f7f4ee" });

    const loader = folded
      ? stage.loadFile(new Blob([folded.pdb], { type: "text/plain" }), { ext: "pdb" })
      : stage.loadFile(`https://files.rcsb.org/download/${pdbId}.cif`, { ext: "cif" });

    loader
      .then((comp) => {
        if (cancelled || !comp) return;
        if (folded) {
          comp.addRepresentation("cartoon", { colorScheme: "bfactor", colorReverse: true });
        } else {
          comp.addRepresentation("cartoon", { colorScheme: "moleculetype" });
          comp.addRepresentation("base", { colorScheme: "moleculetype" });
        }
        stage.handleResize();
        comp.autoView();
        stage.setSpin(true);
      })
      .catch(() => {
        if (!cancelled) setError(folded ? "Could not render the folded model." : `Could not load ${pdbId} from RCSB.`);
      });

    const onResize = () => stage.handleResize();
    window.addEventListener("resize", onResize);
    return () => {
      cancelled = true;
      window.removeEventListener("resize", onResize);
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
      <div ref={ref} className="helix-wrap">
        {error && <div className="viewer-msg">{error}</div>}
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
                      <i style={{ background: CHAIN_COLOR[c.type] ?? "#9a968d" }} />
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
          <select value={region} onChange={(e) => setRegion(e.target.value)} style={{ flex: "none" }}>
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
        {foldErr && <div className="note" style={{ marginTop: 8 }}>{foldErr}</div>}
      </div>
    </>
  );
}
