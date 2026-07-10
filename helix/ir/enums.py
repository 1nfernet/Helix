"""Controlled vocabularies used across the Helix IR.

Every enum is intentionally small for the MVP. Adding a value (e.g. a new
enzyme) should be a one-line change here plus an adapter that knows its PAM —
nothing in the compiler branches on these by hand.
"""

from __future__ import annotations

from enum import Enum


class Modality(str, Enum):
    """The kind of edit being made."""

    CRISPR_KO = "crispr_ko"  # nuclease knockout via NHEJ frameshift
    BASE_EDIT = "base_edit"  # C->T (CBE), A->G (ABE) or C->G (CGBE) within an editing window
    PRIME_EDIT = "prime_edit"  # templated edit via a pegRNA
    HDR = "hdr"  # precise knock-in: nuclease cut + homology-arm donor (ssODN/dsDNA)
    DELETION = "deletion"  # excise a region between two flanking cuts
    CRISPRI = "crispri"  # dCas9-KRAB transcriptional repression (no cut)
    CRISPRA = "crispra"  # dCas9-activator transcriptional activation (no cut)


class Enzyme(str, Enum):
    """The editing enzyme. ``AUTO`` defers the choice to the strategy resolver."""

    AUTO = "auto"
    SPCAS9 = "SpCas9"  # NGG PAM, 20 nt spacer
    SACAS9 = "SaCas9"  # NNGRRT PAM, 21 nt spacer
    CAS12A = "Cas12a"  # TTTV PAM (5' of spacer), 23 nt spacer
    # Engineered SpCas9 variants with relaxed PAMs — expand the targetable space.
    SPG = "SpG"  # NGN PAM
    SPRY = "SpRY"  # NRN PAM (near-PAMless)
    CAS9NG = "Cas9-NG"  # NG PAM
    DCAS9 = "dCas9"  # catalytically dead — CRISPRi/a binding (NGG, no cut)


class BaseEditor(str, Enum):
    """Base-editor chemistry."""

    CBE = "CBE"  # cytosine base editor: C -> T
    ABE = "ABE"  # adenine base editor: A -> G
    CGBE = "CGBE"  # C-to-G base editor (glycosylase): C -> G


class DonorType(str, Enum):
    """HDR donor template format."""

    SSODN = "ssodn"  # single-stranded oligo — small edits/tags, short arms
    DSDNA = "dsdna"  # double-stranded / plasmid — larger cassettes, long arms


# Default homology-arm length (nt) per donor format.
HDR_ARM_LENGTHS = {DonorType.SSODN: 50, DonorType.DSDNA: 300}


# PAM specification per enzyme. The compiler reads this table rather than
# hard-coding "NGG" anywhere, so a new enzyme is a data change.
PAM_TABLE = {
    Enzyme.SPCAS9: {"pam": "NGG", "spacer_length": 20, "pam_is_3prime": True, "cut_offset_from_pam": 3},
    Enzyme.SACAS9: {"pam": "NNGRRT", "spacer_length": 21, "pam_is_3prime": True, "cut_offset_from_pam": 3},
    Enzyme.CAS12A: {"pam": "TTTV", "spacer_length": 23, "pam_is_3prime": False, "cut_offset_from_pam": 18},
    # Relaxed-PAM SpCas9 variants (same geometry, broader PAM).
    Enzyme.SPG: {"pam": "NGN", "spacer_length": 20, "pam_is_3prime": True, "cut_offset_from_pam": 3},
    Enzyme.SPRY: {"pam": "NRN", "spacer_length": 20, "pam_is_3prime": True, "cut_offset_from_pam": 3},
    Enzyme.CAS9NG: {"pam": "NG", "spacer_length": 20, "pam_is_3prime": True, "cut_offset_from_pam": 3},
    Enzyme.DCAS9: {"pam": "NGG", "spacer_length": 20, "pam_is_3prime": True, "cut_offset_from_pam": 3},
}

# CBE/ABE: (target base on the protospacer, product base). Editing window is
# protospacer positions 4-8 (1-based, PAM-distal 5' end = position 1) for SpCas9 BEs.
BASE_EDIT_CHEMISTRY = {
    BaseEditor.CBE: ("C", "T"),
    BaseEditor.ABE: ("A", "G"),
    BaseEditor.CGBE: ("C", "G"),
}
BASE_EDIT_WINDOW = (4, 8)  # inclusive, 1-based protospacer positions


class DeliveryMethod(str, Enum):
    RNP = "rnp"  # MVP: ribonucleoprotein, e.g. nucleofection
    PLASMID = "plasmid"
    LNP = "lnp"
    AAV = "aav"


class ValidationAssay(str, Enum):
    AMPLICON_SEQ = "amplicon_seq"  # MVP: PCR + NGS, analysed by CRISPResso2 later
    T7E1 = "t7e1"


class EditGoal(str, Enum):
    KNOCKOUT = "knockout"


class Strand(str, Enum):
    PLUS = "+"
    MINUS = "-"
