"""Map a parsed Helix AST onto the IR dict consumed by ``spec_from_dict``.

This is the *semantic* layer: it expands the DSL's ergonomic sugar (dotted keys,
``gene(...)`` heads, ``avoid: [homopolymer(>=4), ...]``) into the flat field names
of :class:`helix.ir.spec.ExperimentSpec`. Keeping it separate from parsing means
grammar tweaks and IR-mapping tweaks stay independent.
"""

from __future__ import annotations

from typing import Any, Dict

from helix.frontend.helix_lang import parser as P
from helix.frontend.helix_lang.errors import HelixSyntaxError

_CONSTRAINT_KEYS = {
    ("on_target", "min_efficiency"): "on_target_min_efficiency",
    ("off_target", "max_cfd"): "off_target_max_cfd",
    ("guides", "count"): "guides_count",
    ("gc", "min"): "gc_min",
    ("gc", "max"): "gc_max",
    ("max_homopolymer",): "max_homopolymer",
}

# Named presets that fill sensible constraint/simulate defaults; explicit settings win.
_PROFILES = {
    "strict": {"constraints": {"on_target_min_efficiency": 0.6, "off_target_max_cfd": 0.1,
                               "gc_min": 0.4, "gc_max": 0.75, "max_self_complementarity": 8}},
    "lenient": {"constraints": {"on_target_min_efficiency": 0.3, "off_target_max_cfd": 0.4}},
    "screen": {"constraints": {"guides_count": 6, "on_target_min_efficiency": 0.5, "off_target_max_cfd": 0.2}},
    "quick": {"constraints": {"on_target_min_efficiency": 0.0, "off_target_max_cfd": 0.5},
              "simulate": {"on_target": "heuristic_gc", "off_target": "mock_seed"}},
}


def to_spec_dict(exp: P.Experiment) -> Dict[str, Any]:
    data: Dict[str, Any] = {"name": exp.name}
    target: Dict[str, Any] = {}
    strategy: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    simulate: Dict[str, Any] = {}

    profile = None
    for stmt in exp.body:
        if isinstance(stmt, P.Assign):
            if len(stmt.key) == 1 and stmt.key[0] == "profile":
                profile = _as_str(stmt.value, stmt)
                continue
            _top_assign(stmt, data)
        else:
            _top_block(stmt, target, strategy, constraints, simulate)

    if profile is not None:  # fill preset defaults; explicit settings above already win
        prof = _PROFILES.get(profile)
        if prof is None:
            raise HelixSyntaxError(f"unknown profile '{profile}'; choose one of {', '.join(_PROFILES)}", 1, 1)
        for key, value in prof.get("constraints", {}).items():
            constraints.setdefault(key, value)
        for key, value in prof.get("simulate", {}).items():
            simulate.setdefault(key, value)

    if "gene" not in target:
        raise HelixSyntaxError("a helix spec requires a `target: gene(...) { ... }` block", 1, 1)

    data["target"] = target
    if strategy:
        data["strategy"] = strategy
    if constraints:
        data["constraints"] = constraints
    if simulate:
        data["simulate"] = simulate
    return data


# --- top level ----------------------------------------------------------


def _top_assign(stmt: P.Assign, data: Dict[str, Any]) -> None:
    if len(stmt.key) != 1:
        _err(stmt, f"unexpected dotted key '{'.'.join(stmt.key)}' at top level")
    key = stmt.key[0]
    if key == "organism":
        if isinstance(stmt.value, P.Call):  # human(GRCh38)
            data["organism"] = stmt.value.name
            if stmt.value.args:
                data["genome_build"] = _as_str(stmt.value.args[0], stmt)
        else:
            data["organism"] = _as_str(stmt.value, stmt)
    elif key in ("genome_build", "cell_line", "deliver", "validate"):
        data[key] = _as_str(stmt.value, stmt)
    else:
        _err(stmt, f"unknown top-level setting '{key}'")


def _top_block(stmt, target, strategy, constraints, simulate) -> None:
    if len(stmt.key) != 1:
        _err(stmt, f"unexpected block name '{'.'.join(stmt.key)}'")
    name = stmt.key[0]
    if name == "target":
        _target_block(stmt, target)
    elif name == "strategy":
        _kv_block(stmt, strategy, allowed={"modality", "enzyme", "editor", "donor"})
    elif name == "constraints":
        _constraints_block(stmt, constraints)
    elif name == "simulate":
        _kv_block(
            stmt,
            simulate,
            allowed={"on_target", "off_target", "repair_outcome", "sequence_provider",
                     "base_edit_model", "prime_edit_model", "variant_source"},
        )
    else:
        _err(stmt, f"unknown block '{name}'")


# --- specific blocks ----------------------------------------------------


def _target_block(stmt: P.Block, target: Dict[str, Any]) -> None:
    if stmt.head is None or stmt.head.name != "gene" or not stmt.head.args:
        _err(stmt, "target must be written as `target: gene(SYMBOL) { ... }`")
    target["gene"] = _as_str(stmt.head.args[0], stmt)
    for s in stmt.body:
        if not isinstance(s, P.Assign) or len(s.key) != 1:
            _err(s, "only `goal`, `region`, `sequence` are allowed inside target")
        key = s.key[0]
        if key == "goal":
            target["goal"] = _as_str(s.value, s)
        elif key == "region":
            target["region"] = _region_str(s.value)
        elif key == "sequence":
            target["sequence"] = _as_str(s.value, s)
        elif key == "edit":
            target["edit"] = _as_str(s.value, s)
        elif key == "delete":
            target["delete"] = _as_str(s.value, s)
        elif key == "tss":
            target["tss"] = int(_as_number(s.value, s))
        elif key == "frame":
            target["frame"] = int(_as_number(s.value, s))
        else:
            _err(s, f"unknown target field '{key}'")


def _kv_block(stmt: P.Block, out: Dict[str, Any], allowed: set) -> None:
    for s in stmt.body:
        if not isinstance(s, P.Assign) or len(s.key) != 1:
            _err(s, f"expected simple `key: value` in {stmt.key[0]} block")
        key = s.key[0]
        if key not in allowed:
            _err(s, f"unknown field '{key}' in {stmt.key[0]} block")
        out[key] = _as_str(s.value, s)


def _constraints_block(stmt: P.Block, out: Dict[str, Any]) -> None:
    for s in stmt.body:
        if not isinstance(s, P.Assign):
            _err(s, "constraints must be `key: value` assignments")
        path = tuple(s.key)
        if path == ("avoid",):
            _apply_avoid(s, out)
        elif path in _CONSTRAINT_KEYS:
            out[_CONSTRAINT_KEYS[path]] = _as_number(s.value, s)
        else:
            _err(s, f"unknown constraint '{'.'.join(s.key)}'")


def _apply_avoid(stmt: P.Assign, out: Dict[str, Any]) -> None:
    if not isinstance(stmt.value, P.ListNode):
        _err(stmt, "avoid must be a list, e.g. avoid: [homopolymer(>=4), restriction_site(BsaI)]")
    sites = out.setdefault("avoid_restriction_sites", [])
    for item in stmt.value.items:
        if not isinstance(item, P.Call):
            _err(stmt, "each avoid entry must be a call like homopolymer(>=4)")
        if item.name == "homopolymer":
            arg = item.args[0] if item.args else None
            if isinstance(arg, P.Compare):
                out["max_homopolymer"] = int(arg.value.value)
            elif isinstance(arg, P.Num):
                out["max_homopolymer"] = int(arg.value)
            else:
                _err(stmt, "homopolymer(...) needs a bound, e.g. homopolymer(>=4)")
        elif item.name == "restriction_site":
            sites.append(_as_str(item.args[0], stmt))
        elif item.name == "self_complementary":
            arg = item.args[0] if item.args else None
            if isinstance(arg, P.Compare):
                out["max_self_complementarity"] = int(arg.value.value)
            elif isinstance(arg, P.Num):
                out["max_self_complementarity"] = int(arg.value)
            else:
                _err(stmt, "self_complementary(...) needs a bound, e.g. self_complementary(>=8)")
        elif item.name == "common_variant":
            arg = item.args[0] if item.args else None
            if isinstance(arg, P.Compare):
                out["max_variant_freq"] = float(arg.value.value)
            elif isinstance(arg, P.Num):
                out["max_variant_freq"] = float(arg.value)
            else:
                _err(stmt, "common_variant(...) needs a bound, e.g. common_variant(>=0.01)")
        else:
            _err(stmt, f"unknown avoid rule '{item.name}'")


# --- value coercion -----------------------------------------------------


def _as_str(node: P.Node, stmt) -> str:
    if isinstance(node, P.Str):
        return node.value
    if isinstance(node, P.Ident):
        return node.name
    if isinstance(node, P.Num):
        return str(node.value)
    if isinstance(node, P.Bool):
        return "true" if node.value else "false"
    _err(stmt, f"expected a name or string, got {type(node).__name__}")


def _as_number(node: P.Node, stmt):
    if isinstance(node, P.Num):
        return node.value
    _err(stmt, "expected a number")


def _region_str(node: P.Node) -> str:
    if isinstance(node, P.Call):
        inner = ",".join(_region_str(a) for a in node.args)
        return f"{node.name} {inner}".strip()
    if isinstance(node, P.Range):
        return f"{node.lo}-{node.hi}"
    if isinstance(node, P.Str):
        return node.value
    if isinstance(node, P.Ident):
        return node.name
    if isinstance(node, P.Num):
        return str(node.value)
    return str(node)


def _err(stmt, message: str):
    line = getattr(stmt, "line", 1)
    col = getattr(stmt, "col", 1)
    raise HelixSyntaxError(message, line, col)
