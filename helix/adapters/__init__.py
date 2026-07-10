"""The tool-adapter layer — Helix's integration seam.

Every external capability (sequence retrieval, on-target scoring, off-target
scanning, repair-outcome prediction) is defined as a small :mod:`typing.Protocol`
in :mod:`helix.adapters.base`. The compiler depends only on those Protocols, so a
mock and a real tool (Ensembl, Cas-OFFinder, inDelphi) are interchangeable and
selected by name via :mod:`helix.adapters.registry`.

Each adapter exposes ``name`` and ``version`` so every run is provenance-stamped.
"""
