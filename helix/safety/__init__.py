"""Biosecurity / dual-use gate.

A gene-editing design automation platform must screen intent before doing work.
This is a first-class compiler stage, not an afterthought: :func:`screen`
runs before target resolution and can block a run outright.
"""

from helix.safety.screen import BiosecurityScreen

__all__ = ["BiosecurityScreen"]
