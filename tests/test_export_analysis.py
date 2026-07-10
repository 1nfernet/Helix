"""Tests for order-ready export (oligos) and offline amplicon analysis."""

from helix.analysis.amplicon import analyze_amplicon, parse_reads, synthetic_reads
from helix.compiler.pipeline import compile_spec
from helix.frontend.helix_lang import parse_helix
from helix.report.oligos import cost_estimate, items_to_csv, order_items

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5


def _ko_design():
    spec = parse_helix(
        'helix "k" { organism: human(GRCh38) '
        f'  target: gene(TP53) {{ goal: knockout; sequence: "{SEQ}" }} '
        '  strategy { modality: crispr_ko; enzyme: SpCas9 } '
        '  constraints { on_target.min_efficiency: 0.0; off_target.max_cfd: 0.3; guides.count: 2 } '
        '  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed; repair_outcome: mock_indel } }'
    )
    return compile_spec(spec)


# --- oligo export -------------------------------------------------------


def test_order_items_has_guide_oligos_and_primers():
    items = order_items(_ko_design())
    kinds = {i.kind for i in items}
    assert any("guide oligo (top)" in k for k in kinds)
    assert any("guide oligo (bottom)" in k for k in kinds)
    top = next(i for i in items if i.kind == "guide oligo (top)")
    assert top.sequence.startswith("CACCG") and top.length == len(top.sequence)
    assert any("validation primer" in k for k in kinds)


def test_export_csv_and_cost():
    items = order_items(_ko_design())
    csv = items_to_csv(items)
    assert csv.splitlines()[0].startswith("Name,Kind,Sequence")
    assert len(csv.splitlines()) == len(items) + 1
    cost = cost_estimate(items)
    assert cost["total_usd"] > 0 and cost["item_count"] == len(items)


# --- amplicon analysis --------------------------------------------------


def test_parse_reads_fastq_fasta_plain():
    fastq = "@r1\nACGTACGT\n+\nIIIIIIII\n@r2\nTTTTGGGG\n+\nIIIIIIII"
    assert parse_reads(fastq) == ["ACGTACGT", "TTTTGGGG"]
    fasta = ">a\nACGT\nACGT\n>b\nGGGG"
    assert parse_reads(fasta) == ["ACGTACGT", "GGGG"]
    assert parse_reads("ACGTAC\nGGTTAA\n# comment") == ["ACGTAC", "GGTTAA"]


def test_analyze_detects_editing_and_frameshift():
    ref = SEQ
    cut = len(ref) // 2
    reads = synthetic_reads(ref, cut, n=200, edit_rate=0.7, seed=3)
    analysis, spectrum = analyze_amplicon(ref, reads, cut_pos=cut)
    assert 0.5 < analysis.editing_efficiency < 0.9  # ~0.7 edited (some don't align)
    assert analysis.reads_aligned > 100
    assert analysis.insertions > 0 and analysis.deletions > 0
    assert analysis.frameshift_fraction is not None and 0.0 < analysis.frameshift_fraction <= 1.0
    assert spectrum and spectrum[0]["count"] >= spectrum[-1]["count"]  # sorted by frequency


def test_analyze_all_unedited_is_zero():
    ref = SEQ
    analysis, _ = analyze_amplicon(ref, [ref] * 50, cut_pos=len(ref) // 2)
    assert analysis.editing_efficiency == 0.0 and analysis.modified_reads == 0
