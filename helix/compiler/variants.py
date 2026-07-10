"""Annotate guides with population variants in their protospacer / seed / PAM.

A variant in the PAM or the PAM-proximal seed is the most likely to abolish
binding, so each guide records the overlapping variants and where they fall. The
seed/PAM spans are derived from the enzyme's PAM geometry (both strands).
"""

from __future__ import annotations

from typing import List

from helix.ir.design import GuideCandidate, SeqVariant, VariantHit
from helix.ir.enums import PAM_TABLE, Enzyme, Strand

_SEED_LEN = 10  # PAM-proximal seed bases most sensitive to mismatches/variants


def annotate_variants(guides: List[GuideCandidate], variants: List[SeqVariant], enzyme: Enzyme) -> None:
    e = PAM_TABLE.get(enzyme)
    if not variants or e is None:
        return
    slen, pamlen, is_3p = e["spacer_length"], len(e["pam"]), e["pam_is_3prime"]
    seedlen = min(_SEED_LEN, slen)

    for g in guides:
        wo = g.window_offset
        plus = g.strand is Strand.PLUS
        proto = (wo, wo + slen)
        if is_3p:  # PAM 3' of the protospacer (SpCas9/SaCas9)
            pam = (wo + slen, wo + slen + pamlen) if plus else (wo - pamlen, wo)
            seed = (wo + slen - seedlen, wo + slen) if plus else (wo, wo + seedlen)
        else:  # PAM 5' (Cas12a)
            pam = (wo - pamlen, wo) if plus else (wo + slen, wo + slen + pamlen)
            seed = (wo, wo + seedlen) if plus else (wo + slen - seedlen, wo + slen)

        hits: List[VariantHit] = []
        for v in variants:
            p = v.window_pos
            if pam[0] <= p < pam[1]:
                region = "PAM"
            elif seed[0] <= p < seed[1]:
                region = "seed"
            elif proto[0] <= p < proto[1]:
                region = "protospacer"
            else:
                continue
            hits.append(VariantHit(id=v.id, window_pos=p, region=region, alleles=v.alleles, frequency=v.frequency))
        g.variant_hits = hits
