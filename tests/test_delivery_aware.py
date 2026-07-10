"""Tests for the delivery-aware strategy resolver."""

from helix.agents.strategy import DeliveryAwareStrategyResolver
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec
from helix.ir.enums import Enzyme

# A window with SaCas9 (NNGRRT) PAM sites: 21 nt spacer + TGGAGT, repeated.
SA_SEQ = ("ACGTACGTACGTACGTACGTA" + "TGGAGT") * 4

R = DeliveryAwareStrategyResolver()


def _spec(**over):
    data = {"name": "d", "target": {"gene": "TP53", "sequence": SA_SEQ},
            "strategy": {"enzyme": "auto"}}
    data.update(over)
    return parse_spec(data)


def test_aav_knockout_selects_sacas9():
    assert R.resolve_enzyme(_spec(deliver="aav")) is Enzyme.SACAS9


def test_rnp_knockout_selects_spcas9():
    assert R.resolve_enzyme(_spec(deliver="rnp")) is Enzyme.SPCAS9


def test_base_edit_stays_on_spcas9_even_for_aav():
    assert R.resolve_enzyme(_spec(deliver="aav", strategy={"modality": "base_edit"})) is Enzyme.SPCAS9


def test_honours_explicit_enzyme():
    assert R.resolve_enzyme(_spec(deliver="aav", strategy={"enzyme": "Cas12a"})) is Enzyme.CAS12A


def test_pipeline_aav_designs_with_sacas9():
    spec = _spec(deliver="aav", constraints={"on_target_min_efficiency": 0.0, "off_target_max_cfd": 1.0},
                 simulate={"on_target": "heuristic_gc"})
    design = compile_spec(spec)
    assert design.resolved_enzyme is Enzyme.SACAS9
    assert design.guides  # SaCas9 (NNGRRT) sites enumerated
    # Advisor reconciles: it knows SaCas9 was picked for the AAV request.
    dv = design.delivery
    assert dv.requested == "aav" and dv.requested_suitable is True
    assert any("auto-selected to fit your AAV request" in n for n in dv.notes)


def test_pipeline_swaps_rule_set_1_for_non_spcas9():
    # Rule Set 1 is SpCas9-only; the pipeline should fall back to the heuristic.
    spec = _spec(deliver="aav", constraints={"on_target_min_efficiency": 0.0, "off_target_max_cfd": 1.0},
                 simulate={"on_target": "rule_set_1"})
    design = compile_spec(spec)
    assert design.resolved_enzyme is Enzyme.SACAS9
    assert design.provenance.adapters["on_target"].startswith("heuristic_gc@")
    assert design.guides
