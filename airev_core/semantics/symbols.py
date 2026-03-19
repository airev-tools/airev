"""Semantic data structures — symbols, imports, calls, and the SemanticModel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ImportedSymbol:
    """A symbol brought into scope via import."""

    module: str
    name: str | None
    alias: str | None
    local_name: str
    arena_idx: int
    is_from_import: bool


@dataclass(slots=True, frozen=True)
class DefinedSymbol:
    """A symbol defined locally — function, class, or variable assignment."""

    name: str
    kind: str
    arena_idx: int


@dataclass(slots=True, frozen=True)
class CallSite:
    """A function/method call found in the source."""

    name: str
    receiver: str | None
    full_name: str
    arena_idx: int


@dataclass(slots=True, frozen=True)
class SemanticModel:
    """Immutable semantic summary of a single file. Built once, read by all rules."""

    imports: tuple[ImportedSymbol, ...]
    definitions: tuple[DefinedSymbol, ...]
    calls: tuple[CallSite, ...]
    import_table: dict[str, ImportedSymbol]
    definition_table: dict[str, DefinedSymbol]
