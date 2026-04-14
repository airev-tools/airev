"""hallucinated-api rule — detects calls to non-existent methods on real packages."""

from __future__ import annotations

import ast
import importlib
import importlib.util
from typing import TYPE_CHECKING

from airev_core.arena.node_types import TYPE_CALL
from airev_core.findings.models import (
    Confidence,
    Finding,
    Severity,
    SourceSpan,
)

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.semantics.context import LintContext


def _has_native_extensions(spec: importlib.util.ModuleSpec) -> bool:
    """Check if a module's package directory contains C extensions (.pyd/.so)."""
    if spec.submodule_search_locations is None:
        return False
    from pathlib import Path

    for loc in spec.submodule_search_locations:
        pkg_dir = Path(loc)
        if not pkg_dir.is_dir():
            continue
        for child in pkg_dir.iterdir():
            if child.suffix in (".pyd", ".so"):
                return True
    return False


# Threshold below which AST-only inspection is unreliable for packages with
# native extensions or submodule_search_locations (i.e. real packages).
_MIN_RELIABLE_EXPORT_COUNT = 20


def _get_module_exports_ast(module_name: str) -> frozenset[str] | None:
    """Attempt to read the public names exported by a Python module via AST.

    Returns None if the module is not installed, cannot be inspected, or the
    result is likely incomplete (star imports, C extensions, very few names
    for a package with submodules).  Never executes the module.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except (ModuleNotFoundError, ValueError):
        return None

    if spec is None or spec.origin is None:
        return None

    # If the package contains native C extensions, AST inspection of __init__.py
    # will miss most exports — bail out immediately so the runtime fallback runs.
    if _has_native_extensions(spec):
        return None

    # Read and parse the module's source file
    try:
        with open(spec.origin, encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except (OSError, UnicodeDecodeError):
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.ImportFrom) and node.names:
            for alias in node.names:
                if alias.name == "*":
                    # Can't determine exports from star import via AST
                    return None
                names.add(alias.asname if alias.asname else alias.name)

    # Check __all__ if defined
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, ast.List | ast.Tuple)
                ):
                    all_names: set[str] = set()
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            all_names.add(elt.value)
                    if all_names:
                        return frozenset(all_names)

    # If this is a package (has submodules) but we found very few names,
    # AST inspection likely missed re-exports from submodules — bail out.
    is_package = spec.submodule_search_locations is not None
    if is_package and len(names) < _MIN_RELIABLE_EXPORT_COUNT:
        return None

    return frozenset(names) if names else None


def _get_module_exports_runtime(module_name: str) -> frozenset[str] | None:
    """Fallback: import the module and use dir() to get exports.

    Used when AST inspection fails (frozen modules, C extensions, star imports).
    Only imports modules that are already installed — safe for stdlib and
    third-party packages.
    """
    try:
        mod = importlib.import_module(module_name)
    except Exception:  # noqa: BLE001
        return None
    return frozenset(dir(mod))


def _get_module_exports(module_name: str) -> frozenset[str] | None:
    """Get public names exported by a Python module.

    Tries AST inspection first (no execution), falls back to runtime import.
    """
    result = _get_module_exports_ast(module_name)
    if result is not None:
        return result
    return _get_module_exports_runtime(module_name)


# Cache module exports across rule evaluations within a process
_EXPORT_CACHE: dict[str, frozenset[str] | None] = {}


def _cached_get_exports(module_name: str) -> frozenset[str] | None:
    """Get module exports with caching."""
    if module_name not in _EXPORT_CACHE:
        _EXPORT_CACHE[module_name] = _get_module_exports(module_name)
    return _EXPORT_CACHE[module_name]


class HallucinatedApiRule:
    """Detects calls to methods/functions that don't exist on imported packages.

    AI tools often generate calls to plausible-sounding but non-existent methods
    like np.fast_fourier_transform() or response.getJSON().
    """

    @property
    def id(self) -> str:
        return "hallucinated-api"

    @property
    def severity(self) -> Severity:
        return Severity.ERROR

    @property
    def languages(self) -> frozenset[str] | None:
        return None

    @property
    def target_node_types(self) -> frozenset[int]:
        return frozenset({TYPE_CALL})

    def evaluate(self, arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]:
        """Check if a method call exists on its receiver's module."""
        name_idx = int(arena.name_indices[idx])
        if name_idx == -1:
            return []

        full_name = arena.strings.get(name_idx)

        # Only check calls with a receiver (obj.method pattern)
        dot_pos = full_name.rfind(".")
        if dot_pos == -1:
            return []

        receiver = full_name[:dot_pos]
        method_name = full_name[dot_pos + 1 :]

        # Check if receiver maps to an imported module
        imp = ctx.semantic.import_table.get(receiver)
        if imp is None:
            return []

        # Skip `from X import Y` imports — the receiver is an imported object
        # (class, dict, function, etc.), not the module itself.  We can't know
        # the object's type, so checking module-level exports is wrong here.
        if imp.is_from_import:
            return []

        # Skip if the module is not a third-party import (it might be local)
        if imp.module.startswith("."):
            return []

        # Try to get the module's exports
        exports = _cached_get_exports(imp.module)

        # If we can't determine exports, skip (don't false-positive)
        if exports is None:
            return []

        # Check if the method exists in the module's exports
        if method_name not in exports:
            span = SourceSpan(
                start_line=int(arena.start_lines[idx]),
                start_col=int(arena.start_cols[idx]),
                end_line=int(arena.start_lines[idx]),
                end_col=int(arena.start_cols[idx])
                + (int(arena.end_bytes[idx]) - int(arena.start_bytes[idx])),
                start_byte=int(arena.start_bytes[idx]),
                end_byte=int(arena.end_bytes[idx]),
            )
            return [
                Finding(
                    rule_id=self.id,
                    message=(
                        f"Method '{method_name}' does not exist on module '{imp.module}'. "
                        f"This may be an AI-hallucinated API."
                    ),
                    severity=self.severity,
                    file_path=ctx.file_path,
                    span=span,
                    suggestion=(
                        f"Check the {imp.module} documentation for the correct method name."
                    ),
                    confidence=Confidence.MEDIUM,
                )
            ]

        return []
