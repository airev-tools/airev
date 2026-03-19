"""phantom-import rule — detects imports of packages/modules that don't exist."""

from __future__ import annotations

from typing import TYPE_CHECKING

from airev_core.arena.node_types import TYPE_IMPORT, TYPE_IMPORT_FROM
from airev_core.findings.models import (
    Confidence,
    Finding,
    Severity,
    SourceSpan,
)

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.semantics.context import LintContext


class PhantomImportRule:
    """Detects imports of packages/modules that don't exist.

    AI coding tools frequently hallucinate plausible-sounding package names
    that perfectly mimic the naming conventions of real libraries.
    """

    @property
    def id(self) -> str:
        return "phantom-import"

    @property
    def severity(self) -> Severity:
        return Severity.ERROR

    @property
    def languages(self) -> frozenset[str] | None:
        return None

    @property
    def target_node_types(self) -> frozenset[int]:
        return frozenset({TYPE_IMPORT, TYPE_IMPORT_FROM})

    def evaluate(self, arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]:
        """Check if the imported module actually exists."""
        name_idx = int(arena.name_indices[idx])
        if name_idx == -1:
            return []

        module_name = arena.strings.get(name_idx)

        # Skip relative imports
        if module_name.startswith("."):
            return []

        if not ctx.resolver.module_exists(module_name):
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
                        f"Import '{module_name}' could not be resolved. "
                        f"This package may not exist or may be a hallucinated dependency."
                    ),
                    severity=self.severity,
                    file_path=ctx.file_path,
                    span=span,
                    suggestion=(
                        f"Verify that '{module_name}' is a real package and is installed. "
                        f"Check for typos or AI-generated phantom dependencies."
                    ),
                    confidence=Confidence.HIGH,
                )
            ]

        return []
