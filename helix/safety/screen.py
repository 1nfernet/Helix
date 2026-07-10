"""Rule-based biosecurity screen for the MVP.

Deliberately conservative and transparent. This is a *floor*, not a complete
solution: a production screen would consult curated select-agent/regulated-
sequence databases and a policy model. The point of shipping it now is that the
gate exists in the pipeline from day one and every design carries a verdict.
"""

from __future__ import annotations

from helix.ir.design import SafetyVerdict
from helix.ir.spec import ExperimentSpec

# Minimal illustrative watchlists. Real deployments replace these with curated,
# regularly-updated regulated-organism / regulated-sequence databases.
_WATCHLIST_ORGANISMS = {
    "bacillus anthracis",
    "yersinia pestis",
    "variola",
    "ebolavirus",
    "francisella tularensis",
}
_GERMLINE_MARKERS = {"embryo", "zygote", "germline", "oocyte", "blastocyst"}


class BiosecurityScreen:
    version = "0.1.0"

    def screen(self, spec: ExperimentSpec) -> SafetyVerdict:
        reasons = []

        organism = (spec.organism or "").strip().lower()
        if any(agent in organism for agent in _WATCHLIST_ORGANISMS):
            reasons.append(
                f"Organism '{spec.organism}' matches a regulated-agent watchlist."
            )

        cell_line = (spec.cell_line or "").strip().lower()
        if any(marker in cell_line for marker in _GERMLINE_MARKERS):
            reasons.append(
                f"Cell context '{spec.cell_line}' indicates human germline editing, "
                "which is out of policy."
            )

        return SafetyVerdict(
            allowed=not reasons,
            reasons=reasons,
            screen_version=self.version,
        )
