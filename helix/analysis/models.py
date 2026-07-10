"""IR for the analysis loop: observed editing and predicted-vs-observed reconciliation."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class EditingAnalysis(BaseModel):
    """Observed editing outcomes from amplicon sequencing (normalized CRISPResso2)."""

    editing_efficiency: float = Field(ge=0.0, le=1.0, description="Fraction of reads modified.")
    reads_aligned: int
    modified_reads: int
    unmodified_reads: int
    insertions: int = 0
    deletions: int = 0
    substitutions: int = 0
    frameshift_fraction: Optional[float] = Field(
        default=None, description="Frameshift among coding edits; None if not a coding amplicon."
    )
    analyzer: str


class LoopReconciliation(BaseModel):
    """How the design's predictions held up against the observed data."""

    guide_spacer: str
    predicted_frameshift: float
    observed_frameshift: Optional[float] = None
    frameshift_delta: Optional[float] = None
    frameshift_agrees: Optional[bool] = None
    predicted_on_target: float
    observed_editing_efficiency: float
    tolerance: float
    notes: List[str] = []
