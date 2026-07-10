"""Tests for batch and library compilation."""

from helix.compiler.batch import compile_batch, library_specs
from helix.frontend.loader import parse_spec

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4


def _ko(name):
    return parse_spec({"name": name, "target": {"gene": "TP53", "sequence": SEQ},
                       "constraints": {"on_target_min_efficiency": 0.0, "guides_count": 1}})


def test_compile_batch_compiles_all():
    outs = compile_batch([_ko("a"), _ko("b")])
    assert [o.name for o in outs] == ["a", "b"]
    assert all(o.design is not None and o.error is None for o in outs)


def test_compile_batch_isolates_errors():
    bad = parse_spec({"name": "bad", "target": {"gene": "X", "sequence": SEQ},
                      "strategy": {"modality": "prime_edit"}})  # missing target.edit -> compile error
    outs = compile_batch([_ko("good"), bad])
    assert outs[0].design is not None and outs[0].error is None
    assert outs[1].design is None and outs[1].error  # captured, not raised


def test_library_specs_expands_across_genes():
    base = parse_spec({"name": "lib", "target": {"gene": "TP53", "sequence": SEQ}})
    specs = library_specs(base, ["TP53", "EGFR", "KRAS"])
    assert [s.name for s in specs] == ["lib__TP53", "lib__EGFR", "lib__KRAS"]
    assert [s.target.gene for s in specs] == ["TP53", "EGFR", "KRAS"]
    assert all(s.target.sequence is None for s in specs)  # resolved per-gene via provider
    assert all(s.simulate.sequence_provider == "ensembl" for s in specs)  # switched off inline
