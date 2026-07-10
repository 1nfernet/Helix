"""Server-side run store — persists compiled runs so history survives restarts.

An in-memory index with write-through to a JSON file. Thread-locked (uvicorn may
serve concurrently) and defensive: a corrupt file starts empty, and persistence
failures never break a request. Stores light summaries for listing plus the full
design + protocol for reopening.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

_MAX_RUNS = 200
_SUMMARY_KEYS = ("id", "name", "modality", "feasible", "delivery", "ts")


class RunStore:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._runs: Dict[str, dict] = {}
        self._order: List[str] = []  # newest first
        self._load()

    def _load(self) -> None:
        if not (self.path and self.path.exists()):
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for run in data.get("runs", []):
                self._runs[run["id"]] = run
                self._order.append(run["id"])
        except Exception:
            self._runs.clear()
            self._order.clear()

    def _persist(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            runs = [self._runs[i] for i in self._order]
            self.path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
        except Exception:
            pass  # never let persistence break a request

    @staticmethod
    def _summary(run: dict) -> dict:
        return {k: run.get(k) for k in _SUMMARY_KEYS}

    def _find(self, name: str, modality: str) -> Optional[str]:
        """The most-recent run for the same design (spec name + modality), if any."""
        for rid in self._order:
            r = self._runs[rid]
            if r.get("name") == name and r.get("modality") == modality:
                return rid
        return None

    def add(self, design: dict, protocol: str) -> dict:
        with self._lock:
            name = design.get("spec_name", "design")
            modality = design.get("modality", "")
            # Coalesce by design identity: iterating one design (interactive 3D edits,
            # repeated compiles) updates a single history entry and moves it to the
            # front, instead of piling up near-identical runs. Distinct designs (a
            # different name or modality — including each gene in a library run) stay
            # separate.
            rid = self._find(name, modality) or uuid.uuid4().hex[:12]
            run = {
                "id": rid,
                "name": name,
                "modality": modality,
                "feasible": bool(design.get("feasible")),
                "delivery": (design.get("delivery") or {}).get("recommended"),
                "ts": int(time.time() * 1000),
                "design": design,
                "protocol": protocol,
            }
            self._runs[rid] = run
            self._order = [i for i in self._order if i != rid]
            self._order.insert(0, rid)
            while len(self._order) > _MAX_RUNS:
                self._runs.pop(self._order.pop(), None)
            self._persist()
            return self._summary(run)

    def list(self) -> List[dict]:
        with self._lock:
            return [self._summary(self._runs[i]) for i in self._order]

    def get(self, rid: str) -> Optional[dict]:
        return self._runs.get(rid)

    def delete(self, rid: str) -> bool:
        with self._lock:
            if rid not in self._runs:
                return False
            self._runs.pop(rid)
            self._order = [i for i in self._order if i != rid]
            self._persist()
            return True

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()
            self._order.clear()
            self._persist()
