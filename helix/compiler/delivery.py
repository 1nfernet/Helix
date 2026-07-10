"""Delivery-method optimization.

A transparent, deterministic advisor: given the editor (its cargo size), the
modality, and whether the context looks in vitro or in vivo, it scores the four
delivery methods and recommends one — honouring the real constraints that drive
this choice in practice (AAV's ~4.7 kb packaging limit, RNP's transient low-off-
target profile, LNP for in vivo, plasmid's integration risk).

Not a substitute for judgement; a defensible first pass with the rationale shown.
"""

from __future__ import annotations

from typing import List

from helix.ir.design import DeliveryOption, DeliveryRecommendation
from helix.ir.enums import Enzyme, Modality
from helix.ir.spec import ExperimentSpec

# Approximate editor coding size (kb): nuclease base + modality payload.
_ENZYME_KB = {Enzyme.SPCAS9: 4.1, Enzyme.SACAS9: 3.2, Enzyme.CAS12A: 3.7,
              Enzyme.SPG: 4.1, Enzyme.SPRY: 4.1, Enzyme.CAS9NG: 4.1, Enzyme.DCAS9: 4.1}
_MODALITY_EXTRA_KB = {Modality.CRISPR_KO: 0.0, Modality.BASE_EDIT: 1.6, Modality.PRIME_EDIT: 2.2,
                      Modality.HDR: 0.0,        # HDR uses a plain nuclease; the donor is co-delivered
                      Modality.DELETION: 0.0,   # two guides, one nuclease
                      Modality.CRISPRI: 0.5,    # dCas9 + KRAB repressor
                      Modality.CRISPRA: 1.5}    # dCas9 + VPR/SAM activator
_AAV_LIMIT_KB = 4.7  # single-AAV payload ceiling (CDS + promoter + polyA + gRNA)

# Cell contexts that imply in vivo delivery.
_IN_VIVO_MARKERS = ("in vivo", "vivo", "liver", "muscle", "retina", "brain", "tissue", "tumor")


def cargo_kb(enzyme: Enzyme, modality: Modality) -> float:
    return round(_ENZYME_KB.get(enzyme, 4.1) + _MODALITY_EXTRA_KB.get(modality, 0.0), 1)


def _context(spec: ExperimentSpec) -> str:
    cell = (spec.cell_line or "").lower()
    return "in_vivo" if any(m in cell for m in _IN_VIVO_MARKERS) else "in_vitro"


def recommend_delivery(spec: ExperimentSpec, enzyme: Enzyme) -> DeliveryRecommendation:
    modality = spec.strategy.modality
    kb = cargo_kb(enzyme, modality)
    ctx = _context(spec)
    in_vivo = ctx == "in_vivo"
    is_pe = modality is Modality.PRIME_EDIT
    is_be = modality is Modality.BASE_EDIT

    opts: List[DeliveryOption] = []

    # --- RNP ---
    rnp = 0.35 if in_vivo else 0.85
    rnp_warn = []
    rnp_rat = "Transient, lowest off-target, no genomic integration; ideal for cell lines/primary cells."
    if is_pe:
        rnp -= 0.45
        rnp_warn.append("Prime editing as RNP is inefficient (pegRNA + large PE protein).")
    if in_vivo:
        rnp_warn.append("RNP is hard to deliver in vivo (ex vivo editing excepted).")
    opts.append(DeliveryOption(method="rnp", score=_clamp(rnp), rationale=rnp_rat, warnings=rnp_warn))

    # --- plasmid ---
    plasmid = 0.25 if in_vivo else 0.6
    opts.append(DeliveryOption(
        method="plasmid", score=_clamp(plasmid),
        rationale="Cheap and simple for cell lines; prolonged expression.",
        warnings=["Prolonged expression and integration risk raise off-target editing."],
    ))

    # --- LNP ---
    lnp = 0.8 if in_vivo else 0.4
    lnp_rat = "mRNA + gRNA (or pegRNA); transient, well suited to in vivo (esp. liver)."
    opts.append(DeliveryOption(method="lnp", score=_clamp(lnp), rationale=lnp_rat, warnings=[]))

    # --- AAV ---
    aav = 0.85 if in_vivo else 0.45
    aav_warn = []
    if kb + 0.6 > _AAV_LIMIT_KB:  # +0.6 for promoter/polyA/gRNA overhead
        aav *= 0.4
        aav_warn.append(
            f"Cargo ~{kb} kb + regulatory elements exceeds the ~{_AAV_LIMIT_KB} kb single-AAV "
            "limit — use dual/split-AAV or a smaller enzyme (SaCas9)."
        )
    aav_rat = "Durable expression, strong for in vivo and hard-to-transfect cells."
    opts.append(DeliveryOption(method="aav", score=_clamp(aav), rationale=aav_rat, warnings=aav_warn))

    opts.sort(key=lambda o: (-o.score, o.method))
    recommended = opts[0].method

    requested = spec.deliver.value
    by_method = {o.method: o for o in opts}
    was_auto = spec.strategy.enzyme is Enzyme.AUTO
    aav_viable = kb + 0.6 <= _AAV_LIMIT_KB
    notes: List[str] = []

    # Reconcile the request with the (possibly delivery-driven) enzyme choice.
    if requested == "aav":
        if aav_viable and was_auto and enzyme is not Enzyme.SPCAS9:
            notes.append(
                f"{enzyme.value} was auto-selected to fit your AAV request "
                f"(cargo ~{kb} kb within the {_AAV_LIMIT_KB} kb single-AAV limit)."
            )
        if not aav_viable:
            smaller = "" if enzyme is not Enzyme.SPCAS9 else " (or a smaller enzyme such as SaCas9)"
            notes.append(
                f"AAV cannot single-vector this editor (~{kb} kb); use dual/split-AAV{smaller}."
            )
        elif recommended != "aav":
            notes.append(
                f"AAV is viable with {enzyme.value}; the advisor scores '{recommended}' higher "
                f"for a {ctx.replace('_', ' ')} context — switch if your delivery route is flexible."
            )
        requested_suitable = aav_viable
    else:
        req = by_method.get(requested)
        requested_suitable = req is not None and req.score >= 0.5 and not req.warnings
        if requested != recommended:
            notes.append(
                f"Spec requests '{requested}'; the advisor prefers '{recommended}' "
                f"for a {ctx.replace('_', ' ')} {modality.value} design."
            )
    if is_be and in_vivo:
        notes.append("Base editors are large; LNP (mRNA) or dual-AAV are the usual in vivo routes.")
    if modality is Modality.HDR:
        d = spec.strategy.donor
        if d is not None and d.value == "ssodn":
            notes.append("HDR also needs a donor: co-deliver the ssODN (RNP + ssODN nucleofection is standard).")
        else:
            notes.append("HDR also needs a donor: a dsDNA/plasmid template (or AAV-delivered) supplies the homology arms.")

    return DeliveryRecommendation(
        recommended=recommended,
        requested=requested,
        requested_suitable=requested_suitable,
        cargo_kb=kb,
        context=ctx,
        options=opts,
        notes=notes,
    )


def _clamp(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 3)
