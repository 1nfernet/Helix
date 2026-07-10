// Mirrors the subset of helix.ir.design we render.

export type Format = "helix" | "yaml";

export interface Example {
  name: string;
  format: Format;
  source: string;
}

export interface OffTargetSite {
  sequence: string;
  mismatches: number;
  cfd: number;
  locus: string | null;
}

export interface OffTargetReport {
  max_cfd: number;
  site_count: number;
  sites: OffTargetSite[];
  scorer: string;
}

export interface RepairOutcome {
  frameshift_fraction: number;
  top_outcomes: Record<string, number>[];
  predictor: string;
}

export interface ProteinConsequence {
  kind: string;
  ref_aa: string;
  alt_aa: string;
  codon_change: string;
  label: string;
  note: string;
}

export interface BaseEditOutcome {
  editor: string;
  window: string;
  window_abs_start: number;
  target_base: string;
  product_base: string;
  edited_positions: number[];
  bystander_count: number;
  edited_product: string;
  efficiency: number;
  bystander_proportion: number | null;
  consequence: ProteinConsequence | null;
  predictor: string;
}

export interface HdrDonor {
  donor_type: string;
  strand: string;
  left_arm: string;
  insert: string;
  right_arm: string;
  sequence: string;
  edit: string;
  edit_pos: number;
  cut_to_edit_distance: number;
  arm_length: number;
  pam_disrupted: boolean;
  recut_note: string;
  consequence: ProteinConsequence | null;
  silent_pam_block: boolean | null;
}

export interface RegulationOutcome {
  mode: string;
  tss_offset: number;
  activity_score: number;
  optimal: boolean;
}

export interface DeletionPlan {
  requested_span: string;
  deletion_start: number;
  deletion_end: number;
  deletion_size: number;
  junction: string;
  left_cut: number;
  right_cut: number;
}

export interface VariantHit {
  id: string;
  window_pos: number;
  region: string;
  alleles: string;
  frequency: number | null;
}

export interface ConstraintCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface GuideCandidate {
  spacer: string;
  pam: string;
  strand: string;
  window_offset: number;
  cut_site: number;
  gc_content: number;
  self_complementarity: number;
  on_target_score: number;
  off_target: OffTargetReport;
  repair: RepairOutcome | null;
  base_edit: BaseEditOutcome | null;
  hdr: HdrDonor | null;
  regulation: RegulationOutcome | null;
  variant_hits: VariantHit[];
  checks: ConstraintCheck[];
  passed: boolean;
  composite_score: number;
  rank: number | null;
}

export interface PrimeEditCandidate {
  spacer: string;
  pam: string;
  strand: string;
  nick_position: number;
  pbs: string;
  rtt: string;
  peg_extension: string;
  edit: string;
  on_target_score: number;
  predicted_efficiency: number;
  predictor: string;
  pe3_nick_spacer: string | null;
  pe3_nick_position: number | null;
  consequence: ProteinConsequence | null;
  passed: boolean;
  composite_score: number;
  rank: number | null;
}

export interface ResolvedTarget {
  gene: string;
  genome_build: string;
  sequence: string;
  length: number;
  source: string;
}

export interface SafetyVerdict {
  allowed: boolean;
  reasons: string[];
  screen_version: string;
}

export interface Provenance {
  helix_version: string;
  genome_build: string;
  timestamp_utc: string;
  adapters: Record<string, string>;
  spec_name: string;
}

export interface DeliveryOption {
  method: string;
  score: number;
  rationale: string;
  warnings: string[];
}

export interface DeliveryRecommendation {
  recommended: string;
  requested: string | null;
  requested_suitable: boolean | null;
  cargo_kb: number;
  context: string;
  options: DeliveryOption[];
  notes: string[];
}

export interface ResolvedDesign {
  spec_name: string;
  modality: string;
  resolved_enzyme: string;
  target: ResolvedTarget | null;
  guides: GuideCandidate[];
  selected: GuideCandidate[];
  prime_edits: PrimeEditCandidate[];
  feasible: boolean;
  infeasibility_notes: string[];
  delivery: DeliveryRecommendation | null;
  deletion: DeletionPlan | null;
  safety: SafetyVerdict;
  provenance: Provenance;
}

export interface BatchItemResult {
  name: string | null;
  design?: ResolvedDesign;
  protocol?: string;
  error?: string;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
}

export interface AuthorResult {
  source: string;
  format: Format;
  usage: TokenUsage | null;
  cost: number | null;
  model: string;
}

export interface CritiqueFinding {
  severity: "info" | "warning" | "critical";
  category: string;
  message: string;
  suggestion: string;
}

export interface CritiqueResult {
  summary: string;
  findings: CritiqueFinding[];
  suggested_constraint_edits: Record<string, number | string>;
  dropped_edits: string[];
  revised_source: string | null;
  usage: TokenUsage | null;
  cost: number | null;
  model: string;
}

export interface ResolveResult {
  gene: string;
  genome_build: string;
  length: number;
  source: string;
  sequence: string;
}

export interface AdapterInfo {
  key: string;
  kind: string;
  note?: string;
  configured?: boolean;
  setup?: string;
}

export interface AdapterRole {
  label: string;
  sim_key: string | null;
  prov_key: string | null;
  options: AdapterInfo[];
}

export interface AdaptersResult {
  roles: AdapterRole[];
}

export interface FoldResult {
  name: string;
  region: string;
  residues: number;
  plddt: number;
  pdb: string;
  tool: string;
}

export interface OrderItem {
  name: string;
  kind: string;
  sequence: string;
  length: number;
  note: string;
}

export interface ExportResult {
  items: OrderItem[];
  csv: string;
  cost: { total_usd: number; item_count: number; total_bases: number; note: string };
}

export interface EditingAnalysis {
  editing_efficiency: number;
  reads_aligned: number;
  modified_reads: number;
  unmodified_reads: number;
  insertions: number;
  deletions: number;
  substitutions: number;
  frameshift_fraction: number | null;
  analyzer: string;
}

export interface AnalyzeResult {
  analysis: EditingAnalysis;
  spectrum: { indel: number; count: number }[];
  reconciliation: {
    observed_efficiency: number;
    observed_frameshift: number | null;
    predicted_frameshift?: number;
    frameshift_delta?: number;
    frameshift_agrees?: boolean;
    predicted_on_target?: number;
    predicted_efficiency?: number;
    efficiency_delta?: number;
    efficiency_agrees?: boolean;
    notes: string[];
  };
}

export interface StructureChain {
  type: string;
  id: string;
  name: string;
  length: number;
  sequence?: string;
}

export interface StructureInfo {
  reference_pdb: string;
  available: boolean;
  reason?: string;
  label?: string;
  chains?: StructureChain[];
  confidence?: { ptm: number; iptm: number; plddt: number } | null;
  backend?: string;
}

export interface RunSummary {
  id: string;
  name: string;
  modality: string;
  feasible: boolean;
  delivery: string | null;
  ts: number;
}

export interface CompileResult {
  design: ResolvedDesign;
  protocol: string;
}

export interface ApiError {
  type: string;
  message: string;
  line?: number;
  col?: number;
}
