"""FastAPI backend exposing the Helix compiler to the web frontend.

A thin HTTP layer over :func:`helix.compiler.pipeline.compile_spec` — it parses a
spec (Helix grammar or YAML), compiles it, and returns the resolved design as JSON
plus the rendered protocol. All the real work stays in the library; this module
only translates HTTP <-> IR and shapes errors for the UI.
"""

from helix.server.app import app

__all__ = ["app"]
