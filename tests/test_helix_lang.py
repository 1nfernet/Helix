"""Tests for the Helix grammar frontend."""

from pathlib import Path

import pytest

from helix.compiler.pipeline import compile_spec
from helix.frontend.helix_lang import HelixSyntaxError, parse_helix
from helix.frontend.loader import load_spec

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_grammar_maps_to_ir():
    spec = load_spec(EXAMPLES / "tp53_ko.hx")
    assert spec.name == "TP53_KO_HEK293"
    assert spec.organism == "human" and spec.genome_build == "GRCh38"
    assert spec.target.gene == "TP53"
    assert spec.target.region == "exon 2-4"  # exon(2..4) stringified
    assert spec.strategy.enzyme.value == "auto"


def test_avoid_desugars_to_flat_fields():
    src = """
    helix "x" {
      target: gene(TP53) { sequence: "ACGTACGTACGTACGTACGTACGTGG" }
      constraints { avoid: [ homopolymer(>=5), restriction_site(BsaI) ] }
    }
    """
    spec = parse_helix(src)
    assert spec.constraints.max_homopolymer == 5
    assert spec.constraints.avoid_restriction_sites == ["BsaI"]


def test_dotted_constraint_keys():
    src = """
    helix "x" {
      target: gene(TP53) { sequence: "ACGTACGTACGTACGTACGTACGTGG" }
      constraints { on_target.min_efficiency: 0.7; guides.count: 2 }
    }
    """
    spec = parse_helix(src)
    assert spec.constraints.on_target_min_efficiency == 0.7
    assert spec.constraints.guides_count == 2


def test_yaml_and_hx_compile_to_same_guides():
    hx = compile_spec(load_spec(EXAMPLES / "tp53_ko.hx"))
    yml = compile_spec(load_spec(EXAMPLES / "tp53_ko.yaml"))
    assert [g.spacer for g in hx.selected] == [g.spacer for g in yml.selected]


def test_syntax_error_reports_location():
    with pytest.raises(HelixSyntaxError) as exc:
        parse_helix('helix "x" { target: gene(TP53) { goal knockout } }')
    assert exc.value.line == 1  # missing ':' after goal
    assert "col" in str(exc.value)


def test_unknown_setting_is_rejected():
    with pytest.raises(HelixSyntaxError):
        parse_helix('helix "x" { frobnicate: yes\n target: gene(TP53){} }')


def test_missing_target_is_rejected():
    with pytest.raises(HelixSyntaxError):
        parse_helix('helix "x" { strategy { enzyme: auto } }')


def test_top_level_keyword_is_helix():
    # The block opens with `helix`, not the old `experiment`.
    with pytest.raises(HelixSyntaxError):
        parse_helix('experiment "x" { target: gene(TP53) { sequence: "ACGT" } }')
