"""Rule registry, dispatch table construction, and linear scan engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.findings.models import Finding
    from airev_core.rules.base import FileRule, NodeRule
    from airev_core.semantics.context import LintContext


class RuleRegistry:
    """Collects rules and builds the dispatch table."""

    __slots__ = ("_node_rules", "_file_rules")

    def __init__(self) -> None:
        self._node_rules: list[NodeRule] = []
        self._file_rules: list[FileRule] = []

    def register_node_rule(self, rule: NodeRule) -> None:
        """Register a per-node rule."""
        self._node_rules.append(rule)

    def register_file_rule(self, rule: FileRule) -> None:
        """Register a per-file rule."""
        self._file_rules.append(rule)

    def build_dispatch_table(self, language: str) -> dict[int, list[NodeRule]]:
        """Build O(1) lookup table: node type int -> list of applicable rules."""
        table: dict[int, list[NodeRule]] = {}
        for rule in self._node_rules:
            if rule.languages is None or language in rule.languages:
                for node_type in rule.target_node_types:
                    table.setdefault(node_type, []).append(rule)
        return table

    def get_file_rules(self, language: str) -> list[FileRule]:
        """Return file-level rules applicable to the given language."""
        return [r for r in self._file_rules if r.languages is None or language in r.languages]


def evaluate_file(
    arena: UastArena,
    dispatch_table: dict[int, list[NodeRule]],
    file_rules: list[FileRule],
    ctx: LintContext,
) -> list[Finding]:
    """Single-pass linear scan over the arena + file-level rules.

    Pure function: (arena, rules, context) -> findings.
    """
    findings: list[Finding] = []

    # Phase 1: Linear scan with dictionary jump table dispatch
    for idx in range(arena.count):
        node_type = int(arena.node_types[idx])
        rules = dispatch_table.get(node_type)
        if rules:
            for rule in rules:
                findings.extend(rule.evaluate(arena, idx, ctx))

    # Phase 2: File-level rules (whole-file analysis)
    for file_rule in file_rules:
        findings.extend(file_rule.evaluate(arena, ctx))

    return findings
