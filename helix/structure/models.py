"""Typed models for structural simulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel, Field


@dataclass
class ComplexSpec:
    """The molecular entities of an editing complex, ready to fold."""

    protein: str
    guide_rna: str  # spacer + scaffold, as RNA
    target_dna_sense: str
    target_dna_antisense: str
    label: str


class StructureConfidence(BaseModel):
    ptm: float = Field(ge=0.0, le=1.0, description="Predicted TM-score (whole complex).")
    iptm: float = Field(ge=0.0, le=1.0, description="Interface pTM (protein-nucleic contacts).")
    plddt: float = Field(ge=0.0, le=100.0, description="Mean pLDDT.")


class StructureAssessment(BaseModel):
    label: str
    confidence: StructureConfidence
    well_formed: bool = Field(description="Whether the complex is predicted to assemble confidently.")
    structure_path: Optional[str] = None
    backend: str
    notes: List[str] = Field(default_factory=list)
