"""Rule protocol definitions for airev's detection engine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.findings.models import Finding, Severity
    from airev_core.semantics.context import LintContext


class NodeRule(Protocol):
    """Rule evaluated for specific node types during the linear arena scan."""

    @property
    def id(self) -> str: ...

    @property
    def severity(self) -> Severity: ...

    @property
    def target_node_types(self) -> frozenset[int]: ...

    @property
    def languages(self) -> frozenset[str] | None: ...

    def evaluate(self, arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]: ...


class FileRule(Protocol):
    """Rule evaluated once per file after the linear scan completes."""

    @property
    def id(self) -> str: ...

    @property
    def severity(self) -> Severity: ...

    @property
    def languages(self) -> frozenset[str] | None: ...

    def evaluate(self, arena: UastArena, ctx: LintContext) -> list[Finding]: ...
