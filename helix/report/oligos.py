"""Turn a resolved design into order-ready oligos and a rough cost.

Deterministic: from the selected guides / pegRNAs / donor / primers, emit the DNA
oligos a bench scientist would order — guide cloning oligos (BsmBI/BbsI Golden Gate
into a U6 vector), pegRNA 3' extensions, ssODN donors, and validation primers — as a
structured list plus an IDT-style CSV. Not a substitute for a cloning protocol; a
copy-paste-ready starting point with the assumptions shown.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel

from helix.bio import reverse_complement
from helix.ir.design import ResolvedDesign

_TOP = "CACCG"   # U6 Golden Gate overhang (+1 G) for the top oligo
_BOTTOM = "AAAC"  # complementary overhang for the bottom oligo
_STD_PER_BASE = 0.15   # USD/base, standard desalted oligo
_LONG_PER_BASE = 0.40  # USD/base, long (>60 nt) Ultramer / fragment


class OrderItem(BaseModel):
    name: str
    kind: str
    sequence: str
    length: int
    note: str = ""


def _guide_oligos(tag: str, spacer: str) -> List[OrderItem]:
    sp = spacer.upper()
    top = _TOP + sp
    bottom = _BOTTOM + reverse_complement(sp) + "C"
    return [
        OrderItem(name=f"{tag}_top", kind="guide oligo (top)", sequence=top, length=len(top),
                  note="BsmBI/BbsI Golden Gate into a U6 vector (e.g. lentiCRISPRv2, pX330)"),
        OrderItem(name=f"{tag}_bot", kind="guide oligo (bottom)", sequence=bottom, length=len(bottom),
                  note="anneal with the top oligo"),
    ]


def order_items(design: ResolvedDesign, max_guides: int = 3) -> List[OrderItem]:
    items: List[OrderItem] = []
    if design.modality == "prime_edit":
        for i, p in enumerate(design.prime_edits[:max_guides], 1):
            items += _guide_oligos(f"peg{i}", p.spacer)
            if p.peg_extension:
                items.append(OrderItem(
                    name=f"peg{i}_ext", kind="pegRNA 3' extension (RTT+PBS)",
                    sequence=p.peg_extension, length=len(p.peg_extension), note=f"installs {p.edit}"))
            if p.pe3_nick_spacer:
                items += _guide_oligos(f"peg{i}_pe3", p.pe3_nick_spacer)
    else:
        guides = (design.selected or design.guides)[:max_guides]
        for i, g in enumerate(guides, 1):
            items += _guide_oligos(f"g{i}", g.spacer)
            if g.hdr:
                items.append(OrderItem(
                    name=f"g{i}_donor", kind=f"{g.hdr.donor_type} HDR donor",
                    sequence=g.hdr.sequence, length=len(g.hdr.sequence),
                    note=f"installs {g.hdr.edit}; order as an Ultramer / gene fragment"))

    vp = design.validation_primers
    if vp and vp.forward:
        items.append(OrderItem(name="amp_F", kind="validation primer (fwd)", sequence=vp.forward,
                               length=len(vp.forward), note="amplicon-seq"))
        items.append(OrderItem(name="amp_R", kind="validation primer (rev)", sequence=vp.reverse,
                               length=len(vp.reverse), note=f"{vp.amplicon_length} bp amplicon"))
    return items


def cost_estimate(items: List[OrderItem]) -> dict:
    total = sum(it.length * (_LONG_PER_BASE if it.length > 60 else _STD_PER_BASE) for it in items)
    bases = sum(it.length for it in items)
    return {
        "total_usd": round(total, 2), "item_count": len(items), "total_bases": bases,
        "note": f"rough: standard oligos ~${_STD_PER_BASE}/base, long (>60 nt) ~${_LONG_PER_BASE}/base",
    }


def items_to_csv(items: List[OrderItem]) -> str:
    rows = ["Name,Kind,Sequence (5'->3'),Length,Notes"]
    for it in items:
        note = it.note.replace(",", ";")
        rows.append(f"{it.name},{it.kind},{it.sequence},{it.length},{note}")
    return "\n".join(rows)
