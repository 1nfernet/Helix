"""Closing the loop: analyse wet-lab results and reconcile them with the design.

The compiler *predicts* editing outcomes (on-target efficiency, off-target risk,
inDelphi repair distribution). After a wet-lab run, amplicon sequencing measures
what *actually* happened. This subsystem runs CRISPResso2 on the reads, normalizes
its output, and reconciles predicted vs observed — turning Helix from a one-shot
designer into a design → validate → analyse loop.

CRISPResso2 is a heavy external tool, so it sits behind an injectable backend
(like Cas-OFFinder and inDelphi); the parsers and reconciliation are pure, tested
code.
"""

from helix.analysis.crispresso import (
    Crispresso2Backend,
    Crispresso2NotConfigured,
    CrispressoAnalyzer,
    parse_frameshift_analysis,
    parse_quantification,
)
from helix.analysis.models import EditingAnalysis, LoopReconciliation
from helix.analysis.reconcile import reconcile

__all__ = [
    "EditingAnalysis",
    "LoopReconciliation",
    "CrispressoAnalyzer",
    "Crispresso2Backend",
    "Crispresso2NotConfigured",
    "parse_quantification",
    "parse_frameshift_analysis",
    "reconcile",
]
