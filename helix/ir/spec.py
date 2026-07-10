"""The *intent* layer: the parsed Helix DSL.

An ``ExperimentSpec`` is what a scientist authors and reviews in git. It is
deliberately declarative — it says *what* is wanted and under *what constraints*,
never *how* to compute it. The compiler and agents own the "how".

For the MVP the DSL surface is YAML (see :mod:`helix.frontend.loader`); a
dedicated grammar can compile to these same models later without touching the
compiler.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from helix.ir.enums import (
    BaseEditor,
    DeliveryMethod,
    DonorType,
    EditGoal,
    Enzyme,
    Modality,
    ValidationAssay,
)


class TargetSpec(BaseModel):
    """What to edit.

    For the MVP the target sequence is provided inline so the pipeline is fully
    deterministic and offline. A coordinate-driven sequence provider (Ensembl)
    resolves ``gene`` + ``region`` into the same ``sequence`` later.
    """

    gene: str
    goal: EditGoal = EditGoal.KNOCKOUT
    region: Optional[str] = Field(
        default=None,
        description="Human-readable constraint on the edit window, e.g. 'exon 2-4'.",
    )
    sequence: Optional[str] = Field(
        default=None,
        description="Inline target DNA (5'->3', plus strand). MVP source of truth.",
    )
    edit: Optional[str] = Field(
        default=None,
        description="Desired prime/HDR edit, e.g. 'A>G @ 12' (ref>alt @ 1-based window position).",
    )
    delete: Optional[str] = Field(
        default=None,
        description="Region to excise (dual-cut deletion), e.g. '40..90' (1-based inclusive).",
    )
    tss: Optional[int] = Field(
        default=None,
        description="1-based transcription start site in the window (CRISPRi/a); defaults to the centre.",
    )
    frame: Optional[int] = Field(
        default=None,
        ge=0,
        le=2,
        description="Reading-frame phase of window position 0 (0/1/2); enables protein-consequence calls. "
        "The window is treated as the coding/sense strand.",
    )

    model_config = {"extra": "forbid"}


class StrategySpec(BaseModel):
    modality: Modality = Modality.CRISPR_KO
    enzyme: Enzyme = Enzyme.AUTO
    editor: Optional[BaseEditor] = Field(
        default=None, description="Base-editor chemistry (required for modality base_edit)."
    )
    donor: Optional[DonorType] = Field(
        default=None, description="HDR donor format ssodn/dsdna (required for modality hdr)."
    )

    model_config = {"extra": "forbid"}


class Constraints(BaseModel):
    """Hard requirements the resolved design must satisfy.

    These make optimisation first-class: the compiler *solves* against them and
    reports infeasibility explicitly, rather than silently returning whatever it
    found.
    """

    on_target_min_efficiency: float = Field(0.5, ge=0.0, le=1.0)
    off_target_max_cfd: float = Field(0.2, ge=0.0, le=1.0)
    guides_count: int = Field(3, ge=1)
    max_homopolymer: int = Field(
        4, ge=2, description="Reject spacers with a run of >= this many identical bases."
    )
    gc_min: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum spacer GC fraction.")
    gc_max: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Maximum spacer GC fraction.")
    max_self_complementarity: Optional[int] = Field(
        default=None, ge=2, description="Reject spacers with an internal complementary stem >= this."
    )
    max_variant_freq: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Reject guides with a population variant at >= this frequency in the seed/PAM.",
    )
    avoid_restriction_sites: List[str] = Field(
        default_factory=list,
        description="Enzyme names (e.g. 'BsaI') whose recognition site must be absent.",
    )

    model_config = {"extra": "forbid"}


class SimulateSpec(BaseModel):
    """Which adapters back each in-silico step. Values are registry keys
    (see :mod:`helix.adapters.registry`), not implementations — swapping a mock
    for a real tool is a one-word edit in the spec."""

    on_target: str = "heuristic_gc"
    off_target: str = "mock_seed"
    repair_outcome: str = "mock_indel"
    sequence_provider: str = "inline"
    base_edit_model: str = "window_heuristic"  # or "behive"
    prime_edit_model: str = "pe_heuristic"  # or "pridict"
    variant_source: str = "none"  # or "ensembl" — flag population variants in the seed/PAM

    model_config = {"extra": "forbid"}


class ExperimentSpec(BaseModel):
    """The complete, self-contained description of one editing experiment."""

    name: str
    organism: str = "human"
    genome_build: str = "GRCh38"
    cell_line: Optional[str] = None

    target: TargetSpec
    strategy: StrategySpec = Field(default_factory=StrategySpec)
    constraints: Constraints = Field(default_factory=Constraints)
    simulate: SimulateSpec = Field(default_factory=SimulateSpec)

    deliver: DeliveryMethod = DeliveryMethod.RNP
    validate_with: ValidationAssay = ValidationAssay.AMPLICON_SEQ

    model_config = {"extra": "forbid"}
