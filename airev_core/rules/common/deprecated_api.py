"""Deprecated API detection rule — checks calls against a curated deprecation database."""

from __future__ import annotations

from typing import TYPE_CHECKING

from airev_core.arena.node_types import TYPE_CALL, TYPE_IMPORT_FROM
from airev_core.findings.models import Confidence, Finding, SourceSpan
from airev_core.rules.common.deprecation_db import DEPRECATED_INDEX

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.findings.models import Severity
    from airev_core.semantics.context import LintContext


class DeprecatedApiRule:
    """Detects usage of deprecated APIs using a curated database.

    Checks both:
    1. `from module import deprecated_name` (import-level)
    2. `module.deprecated_name()` (call-level)
    """

    @property
    def id(self) -> str:
        return "deprecated-api"

    @property
    def severity(self) -> Severity:
        from airev_core.findings.models import Severity as Sev

        return Sev.WARNING

    @property
    def target_node_types(self) -> frozenset[int]:
        return frozenset({TYPE_CALL, TYPE_IMPORT_FROM})

    @property
    def languages(self) -> frozenset[str] | None:
        return None

    def evaluate(self, arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]:
        """Check if a call or import references a deprecated API."""
        node_type = int(arena.node_types[idx])

        if node_type == TYPE_IMPORT_FROM:
            return self._check_import(arena, idx, ctx)
        if node_type == TYPE_CALL:
            return self._check_call(arena, idx, ctx)
        return []

    def _check_import(self, arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]:
        """Check `from module import name` against deprecation DB."""
        name = arena.get_name(idx)
        if not name:
            return []

        # Parse "module:name" or just module name
        # The semantic model has better info — use import table
        findings: list[Finding] = []
        for imp in ctx.semantic.imports:
            if imp.arena_idx != idx:
                continue
            if not imp.is_from_import or imp.name is None:
                continue

            lang = _normalize_language(ctx.language)
            entry = DEPRECATED_INDEX.get((imp.module, imp.name))
            if entry is not None and entry.language == lang:
                findings.append(
                    Finding(
                        rule_id=self.id,
                        message=(
                            f"'{imp.module}.{imp.name}' is deprecated ({entry.reason}). "
                            f"Use {entry.replacement} instead."
                        ),
                        severity=entry.severity,
                        file_path=ctx.file_path,
                        span=SourceSpan(
                            start_line=int(arena.start_lines[idx]),
                            start_col=int(arena.start_cols[idx]),
                            end_line=int(arena.start_lines[idx]),
                            end_col=int(arena.start_cols[idx]) + len(imp.name),
                            start_byte=int(arena.start_bytes[idx]),
                            end_byte=int(arena.end_bytes[idx]),
                        ),
                        suggestion=f"Replace with {entry.replacement}",
                        confidence=Confidence.HIGH,
                    )
                )
        return findings

    def _check_call(self, arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]:
        """Check `module.method()` calls against deprecation DB."""
        name = arena.get_name(idx)
        if not name or "." not in name:
            return []

        parts = name.rsplit(".", 1)
        if len(parts) != 2:
            return []

        receiver, method = parts

        # Resolve receiver to module via import table
        imp = ctx.semantic.import_table.get(receiver)
        if imp is None:
            return []

        module_name = imp.module
        lang = _normalize_language(ctx.language)
        entry = DEPRECATED_INDEX.get((module_name, method))
        if entry is None or entry.language != lang:
            return []

        return [
            Finding(
                rule_id=self.id,
                message=(
                    f"'{module_name}.{method}()' is deprecated ({entry.reason}). "
                    f"Use {entry.replacement} instead."
                ),
                severity=entry.severity,
                file_path=ctx.file_path,
                span=SourceSpan(
                    start_line=int(arena.start_lines[idx]),
                    start_col=int(arena.start_cols[idx]),
                    end_line=int(arena.start_lines[idx]),
                    end_col=int(arena.start_cols[idx]) + len(name),
                    start_byte=int(arena.start_bytes[idx]),
                    end_byte=int(arena.end_bytes[idx]),
                ),
                suggestion=f"Replace with {entry.replacement}",
                confidence=Confidence.HIGH,
            )
        ]


def _normalize_language(language: str) -> str:
    """Normalize typescript -> javascript for deprecation lookups."""
    if language == "typescript":
        return "javascript"
    return language
