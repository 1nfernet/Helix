"""End-to-end and behavioural tests for the compiler."""

from pathlib import Path

from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import load_spec, parse_spec

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "tp53_ko.yaml"


def _base_spec_dict():
    return {
        "name": "unit",
        "target": {"gene": "TP53", "sequence": "ATGGCCGATTACGGCTAACCGGATCGATCGG" * 4},
    }


def test_example_compiles_and_is_reproducible():
    spec = load_spec(EXAMPLE)
    d1 = compile_spec(spec)
    d2 = compile_spec(spec)
    assert d1.safety.allowed
    assert d1.target is not None
    assert d1.guides, "expected candidate guides"
    # Determinism: same spec -> identical design (timestamp aside).
    assert d1.model_dump(exclude={"provenance"}) == d2.model_dump(exclude={"provenance"})


def test_auto_enzyme_resolves_to_spcas9():
    spec = load_spec(EXAMPLE)
    design = compile_spec(spec)
    assert design.resolved_enzyme.value == "SpCas9"


def test_selected_guides_satisfy_constraints():
    spec = load_spec(EXAMPLE)
    design = compile_spec(spec)
    for g in design.selected:
        assert g.on_target_score >= spec.constraints.on_target_min_efficiency
        assert g.off_target.max_cfd <= spec.constraints.off_target_max_cfd
        assert g.passed


def test_ranking_is_monotonic():
    design = compile_spec(parse_spec(_base_spec_dict()))
    scores = [g.composite_score for g in design.guides]
    assert scores == sorted(scores, reverse=True)
    assert [g.rank for g in design.guides] == list(range(1, len(design.guides) + 1))


def test_safety_screen_blocks_germline():
    d = _base_spec_dict()
    d["cell_line"] = "human embryo"
    design = compile_spec(parse_spec(d))
    assert not design.safety.allowed
    assert design.target is None
    assert not design.selected


def test_infeasible_when_constraints_impossible():
    d = _base_spec_dict()
    d["constraints"] = {"on_target_min_efficiency": 0.999, "guides_count": 5}
    design = compile_spec(parse_spec(d))
    assert not design.feasible
    assert design.infeasibility_notes
