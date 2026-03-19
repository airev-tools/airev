"""LintContext — immutable analysis bundle passed to every rule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.semantics.resolver import ImportResolver
    from airev_core.semantics.symbols import SemanticModel


@dataclass(slots=True, frozen=True)
class LintContext:
    """Immutable bundle passed to every rule. Contains everything needed for evaluation."""

    arena: UastArena
    semantic: SemanticModel
    file_path: str
    language: str
    source: bytes
    resolver: ImportResolver
