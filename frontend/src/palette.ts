/** Colour constants shared by the 2D chrome and the WebGL viewers.
 *
 * The viewers can't read CSS custom properties, so the values that have to exist
 * in both worlds live here once and are derived — never re-typed. Before this
 * module the nucleotide palette was written out twice (the 3D scene and the
 * legend that explains it), which meant the legend could quietly start lying
 * about the picture next to it. Keep it that way: one literal, two consumers.
 */

/** The nucleotide palette — the one sanctioned categorical ramp (DESIGN.md §2).
 *
 * Base identity only, in the sequence and 3D views. Hues are separated along the
 * blue↔orange axis, the axis that survives red-green colour blindness, and every
 * use pairs the colour with its letter, so hue is reinforcement and never the
 * sole encoding. These are deliberately *not* the status trio: a green base does
 * not mean "pass". */
export const BASE_HEX = {
  A: "#2f7d5f",
  T: "#b8553a",
  G: "#3768ab",
  C: "#a87a24",
  N: "#7c828c",
} as const;

export type Base = keyof typeof BASE_HEX;

/** Legend / display order — the conventional A·T·G·C pairing order, not alphabetical. */
export const BASES: readonly Base[] = ["A", "T", "G", "C"] as const;

const toInt = (hex: string) => parseInt(hex.slice(1), 16);

/** The same palette as three.js integers. Derived, so it cannot drift from BASE_HEX. */
export const BASE_INT: Record<Base, number> = Object.fromEntries(
  Object.entries(BASE_HEX).map(([k, v]) => [k, toInt(v)])
) as Record<Base, number>;

/** Molecule-type colours for the Cas9 complex viewer.
 *
 * Deliberately the *same* four hues as the nucleotide ramp rather than a fifth
 * palette: the two axes never appear in the same view (Table/3D helix vs. the
 * Complex tab), so reusing them keeps the categorical vocabulary to one small
 * set. The mapping keeps each molecule's established role — protein blue, the
 * guide RNA warm, the target DNA green.
 *
 * NGL takes CSS colour strings, not ints. */
export const CHAIN_HEX: Record<string, string> = {
  protein: BASE_HEX.G,
  rna: BASE_HEX.T,
  dna: BASE_HEX.A,
  other: BASE_HEX.N,
};

/** The complex viewer's backdrop. Flat --surface-2, the tone the helix viewer's
 *  fog fades into, so the two 3D tabs read as the same stage. */
export const STAGE_BG = "#eef1f6";

/** Scene furniture for the 3D viewers, mirroring the CSS tokens of the same name. */
export const SCENE = {
  /** --surface-2: the viewer backdrop; fog fades distant strands into it. */
  fog: toInt("#eef1f6"),
  /** --border-strong: the sugar-phosphate backbone, a neutral armature. */
  backbone: toInt("#ccd2dd"),
  /** --accent: the cut/edit site marker. The signature indigo, same as every
   *  other "this is the thing you're acting on" cue in the app. */
  accent: toInt("#5b53e0"),
  /** --accent-hover: the live hover/drag ring over a pickable base. */
  accentHover: toInt("#4840c4"),
  /** --text-muted: hover ring over a base that can't be edited. */
  inert: toInt("#666d76"),
} as const;
