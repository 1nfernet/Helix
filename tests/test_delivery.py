"""Tests for the delivery-optimization advisor."""

from helix.compiler.delivery import cargo_kb, recommend_delivery
from helix.frontend.loader import parse_spec
from helix.ir.enums import Enzyme, Modality


def _spec(**over):
    data = {"name": "d", "target": {"gene": "TP53", "sequence": "ACGT" * 8}}
    data.update(over)
    return parse_spec(data)


def test_cargo_size_grows_with_modality():
    assert cargo_kb(Enzyme.SPCAS9, Modality.CRISPR_KO) == 4.1
    assert cargo_kb(Enzyme.SACAS9, Modality.CRISPR_KO) < cargo_kb(Enzyme.SPCAS9, Modality.CRISPR_KO)
    assert cargo_kb(Enzyme.SPCAS9, Modality.BASE_EDIT) > cargo_kb(Enzyme.SPCAS9, Modality.CRISPR_KO)
    assert cargo_kb(Enzyme.SPCAS9, Modality.PRIME_EDIT) > cargo_kb(Enzyme.SPCAS9, Modality.BASE_EDIT)


def test_in_vitro_knockout_prefers_rnp():
    rec = recommend_delivery(_spec(cell_line="HEK293T"), Enzyme.SPCAS9)
    assert rec.context == "in_vitro"
    assert rec.recommended == "rnp"


def test_in_vivo_avoids_rnp():
    rec = recommend_delivery(_spec(cell_line="mouse liver"), Enzyme.SPCAS9)
    assert rec.context == "in_vivo"
    assert rec.recommended in ("aav", "lnp") and rec.recommended != "rnp"


def test_base_editor_flags_aav_packaging_limit():
    rec = recommend_delivery(_spec(cell_line="HEK293T", strategy={"modality": "base_edit"}), Enzyme.SPCAS9)
    aav = next(o for o in rec.options if o.method == "aav")
    assert aav.warnings and any("single-AAV" in w for w in aav.warnings)


def test_prime_editing_warns_on_rnp_and_prefers_plasmid_in_vitro():
    rec = recommend_delivery(_spec(cell_line="HEK293T", strategy={"modality": "prime_edit"}), Enzyme.SPCAS9)
    rnp = next(o for o in rec.options if o.method == "rnp")
    assert rnp.warnings  # PE-as-RNP is flagged
    assert rec.recommended == "plasmid"


def test_requested_method_note_when_suboptimal():
    rec = recommend_delivery(_spec(cell_line="HEK293T", deliver="aav"), Enzyme.SPCAS9)
    assert rec.requested == "aav" and rec.recommended == "rnp"
    assert rec.notes
