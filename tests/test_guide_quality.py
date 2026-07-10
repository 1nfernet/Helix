"""Tests for guide-quality constraints (GC window, self-complementarity) and DSL profiles."""

import pytest

from helix.bio import self_complementarity
from helix.compiler.pipeline import compile_spec
from helix.frontend.helix_lang import HelixSyntaxError, parse_helix

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5


def _spec(extra_constraints: str = "", top: str = "") -> str:
    return (
        f'helix "q" {{ organism: human(GRCh38) {top} '
        f'  target: gene(TP53) {{ goal: knockout; sequence: "{SEQ}" }} '
        "  strategy { modality: crispr_ko; enzyme: SpCas9 } "
        f"  constraints {{ guides.count: 1 {extra_constraints} }} "
        "  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed; repair_outcome: mock_indel } }"
    )


def test_self_complementarity_metric():
    assert self_complementarity("AAAAAAAA") == 0  # A's complement is T; none present
    assert self_complementarity("GGGGGCCCCC") == 5  # GGGGG ↔ CCCCC stem
    assert self_complementarity("AAAAATTTTT") == 5  # AAAAA ↔ TTTTT hairpin


def test_gc_and_selfcomp_are_checked_and_reported():
    d = compile_spec(parse_helix(_spec("gc.min: 0.4; gc.max: 0.75; avoid: [self_complementary(>=8)]")))
    g = d.guides[0]
    assert g.self_complementarity >= 0
    names = {c.name for c in g.checks}
    assert {"gc_min", "gc_max", "max_self_complementarity"} <= names


def test_gc_constraint_can_make_infeasible():
    # An impossible GC window rejects every guide.
    d = compile_spec(parse_helix(_spec("gc.min: 0.99")))
    assert not d.feasible
    assert all(not c.passed for g in d.guides for c in g.checks if c.name == "gc_min")


def test_profile_sets_defaults_and_explicit_overrides():
    s = parse_helix(_spec(top="profile: strict"))
    assert s.constraints.gc_min == 0.4 and s.constraints.gc_max == 0.75
    assert s.constraints.max_self_complementarity == 8
    assert s.constraints.on_target_min_efficiency == 0.6
    # an explicit constraint wins over the profile default
    s2 = parse_helix(_spec("on_target.min_efficiency: 0.2", top="profile: strict"))
    assert s2.constraints.on_target_min_efficiency == 0.2 and s2.constraints.gc_max == 0.75


def test_unknown_profile_errors():
    with pytest.raises(HelixSyntaxError):
        parse_helix(_spec(top="profile: nonsense"))
