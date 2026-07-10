"""Base-editing designer (CBE/ABE).

Base editors convert a target base (C->T for CBE, A->G for ABE) within the
protospacer editing window (positions 4-8 for SpCas9 BEs). This designer
enumerates SpCas9 guides, keeps those with an editable base in the window, and
reports the conversion plus bystanders. The *window analysis* is exact; the
*efficiency and bystander proportion* come from a learned model behind the
``BaseEditBackend`` seam (heuristic by default, BE-Hive when configured).
"""

from __future__ import annotations

from typing import List, Optional

from helix.adapters.base import OffTargetScorer, OnTargetScorer, ScorerContextError
from helix.adapters.base_edit_model import BaseEditBackend, HeuristicBaseEditBackend
from helix.bio import gc_content, iter_pam_sites, reverse_complement
from helix.compiler.consequence import base_edit_consequence
from helix.compiler.guide_designer import _mer30
from helix.ir.design import BaseEditOutcome, GuideCandidate, ResolvedTarget
from helix.ir.enums import BASE_EDIT_CHEMISTRY, BASE_EDIT_WINDOW, BaseEditor, Enzyme, Strand

_PAM = "NGG"
_SLEN = 20


def design_base_edits(
    target: ResolvedTarget,
    enzyme: Enzyme,
    editor: BaseEditor,
    on_target: OnTargetScorer,
    off_target: OffTargetScorer,
    model: Optional[BaseEditBackend] = None,
    target_pos: Optional[int] = None,
) -> List[GuideCandidate]:
    """Enumerate base-editing guides.

    If ``target_pos`` (0-based, in target-sequence coordinates) is given, keep
    only guides whose editing window covers that position — i.e. guides that can
    edit the specific base the user picked.
    """
    if enzyme is not Enzyme.SPCAS9:
        raise NotImplementedError("Base editing supports SpCas9-derived editors only.")
    model = model or HeuristicBaseEditBackend()
    target_base, product_base = BASE_EDIT_CHEMISTRY[editor]
    wlo, whi = BASE_EDIT_WINDOW  # 1-based inclusive
    wlen = whi - wlo + 1

    seq = target.sequence
    length = len(seq)
    out: List[GuideCandidate] = []

    for (start, spacer, pam_seq, mer), strand, window_offset in _iter_guides(
        seq, reverse_complement(seq), length
    ):
        analysis = _analyze_window(spacer, target_base, product_base, wlo, whi)
        if analysis is None:
            continue
        window, positions, edited_product = analysis
        cand = _build(target, spacer, pam_seq, strand, window_offset, mer, editor,
                      target_base, product_base, window, positions, edited_product,
                      model, on_target, off_target)
        if cand is None:
            continue
        if target_pos is not None:
            be = cand.base_edit
            if be is None or not (be.window_abs_start <= target_pos < be.window_abs_start + wlen):
                continue
        out.append(cand)
    return out


def _iter_guides(seq, rc, length):
    for start, spacer, pam_seq in iter_pam_sites(seq, _PAM, _SLEN, True):
        yield (start, spacer, pam_seq, _mer30(seq, start)), Strand.PLUS, start
    for rc_start, spacer, pam_seq in iter_pam_sites(rc, _PAM, _SLEN, True):
        yield (rc_start, spacer, pam_seq, _mer30(rc, rc_start)), Strand.MINUS, length - rc_start - _SLEN


def _analyze_window(spacer, target_base, product_base, wlo, whi):
    window = spacer[wlo - 1 : whi]  # positions wlo..whi (1-based)
    positions = [wlo + i for i, b in enumerate(window) if b == target_base]
    if not positions:
        return None
    return window, positions, window.replace(target_base, product_base)


def _build(target, spacer, pam, strand, window_offset, mer, editor, target_base, product_base,
           window, positions, edited_product, model, on_target, off_target) -> Optional[GuideCandidate]:
    try:
        on = on_target.score(spacer, mer)
    except ScorerContextError:
        return None
    off = off_target.scan(spacer, target.genome_build)
    pred = model.predict(spacer, editor.value, positions)

    wlo, whi = BASE_EDIT_WINDOW
    # Absolute (target-sequence) start of the 5-nt editing window, per strand.
    window_abs_start = (
        window_offset + (wlo - 1) if strand is Strand.PLUS else window_offset + (_SLEN - whi)
    )

    # Coding-strand (window) changes for each edited base, strand-resolved. A plus
    # guide edits the base directly; a minus guide edits the complementary base, so
    # the window (plus/coding) strand sees the complement change at the mirrored position.
    if strand is Strand.PLUS:
        changes = [(window_offset + (p - 1), product_base) for p in positions]
    else:
        comp_product = reverse_complement(product_base)
        changes = [(window_offset + (_SLEN - p), comp_product) for p in positions]
    consequence = base_edit_consequence(target.sequence, target.frame, changes)

    outcome = BaseEditOutcome(
        editor=editor.value,
        window=window,
        window_abs_start=window_abs_start,
        target_base=target_base,
        product_base=product_base,
        edited_positions=positions,
        bystander_count=max(0, len(positions) - 1),
        edited_product=edited_product,
        efficiency=pred.efficiency,
        bystander_proportion=pred.bystander_proportion,
        consequence=consequence,
        predictor=pred.predictor,
    )
    composite = on * (1.0 - off.max_cfd) * pred.efficiency
    center = window_offset + 5 if strand is Strand.PLUS else window_offset + _SLEN - 6
    return GuideCandidate(
        spacer=spacer,
        pam=pam,
        strand=strand,
        window_offset=window_offset,
        cut_site=center,
        gc_content=round(gc_content(spacer), 3),
        on_target_score=round(on, 3),
        off_target=off,
        base_edit=outcome,
        composite_score=round(composite, 4),
    )
