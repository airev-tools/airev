"""Tests for RuleRegistry and evaluate_file."""

from __future__ import annotations

from airev_core.arena.node_types import TYPE_CALL, TYPE_IMPORT
from airev_core.arena.uast_arena import UastArena
from airev_core.findings.models import (
    Finding,
    Severity,
    SourceSpan,
)
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext


class _StubResolver:
    def module_exists(self, module_name: str) -> bool:
        return True


def _make_finding(rule_id: str = "test-rule") -> Finding:
    return Finding(
        rule_id=rule_id,
        message="test finding",
        severity=Severity.ERROR,
        file_path="test.py",
        span=SourceSpan(1, 0, 1, 10, 0, 10),
    )


class _MockNodeRule:
    def __init__(self, target_types: frozenset[int], lang: frozenset[str] | None = None) -> None:
        self._target_types = target_types
        self._lang = lang
        self._calls: list[int] = []

    @property
    def id(self) -> str:
        return "mock-node-rule"

    @property
    def severity(self) -> Severity:
        return Severity.ERROR

    @property
    def target_node_types(self) -> frozenset[int]:
        return self._target_types

    @property
    def languages(self) -> frozenset[str] | None:
        return self._lang

    def evaluate(self, arena: UastArena, idx: int, ctx: LintContext) -> list[Finding]:
        self._calls.append(idx)
        return [_make_finding()]


class _MockFileRule:
    def __init__(self, lang: frozenset[str] | None = None) -> None:
        self._lang = lang

    @property
    def id(self) -> str:
        return "mock-file-rule"

    @property
    def severity(self) -> Severity:
        return Severity.ERROR

    @property
    def languages(self) -> frozenset[str] | None:
        return self._lang

    def evaluate(self, arena: UastArena, ctx: LintContext) -> list[Finding]:
        return [_make_finding("file-finding")]


def _make_ctx(arena: UastArena, language: str = "python") -> LintContext:
    builder = SemanticBuilder()
    semantic = builder.build(arena, language)
    return LintContext(
        arena=arena,
        semantic=semantic,
        file_path="test.py",
        language=language,
        source=b"",
        resolver=_StubResolver(),  # type: ignore[arg-type]
    )


class TestRuleRegistry:
    def test_register_and_build_dispatch(self) -> None:
        reg = RuleRegistry()
        rule = _MockNodeRule(frozenset({TYPE_CALL}))
        reg.register_node_rule(rule)
        table = reg.build_dispatch_table("python")
        assert TYPE_CALL in table
        assert rule in table[TYPE_CALL]

    def test_multiple_rules_different_types(self) -> None:
        reg = RuleRegistry()
        r1 = _MockNodeRule(frozenset({TYPE_CALL}))
        r2 = _MockNodeRule(frozenset({TYPE_IMPORT}))
        reg.register_node_rule(r1)
        reg.register_node_rule(r2)
        table = reg.build_dispatch_table("python")
        assert TYPE_CALL in table
        assert TYPE_IMPORT in table

    def test_language_filtering(self) -> None:
        reg = RuleRegistry()
        py_only = _MockNodeRule(frozenset({TYPE_CALL}), frozenset({"python"}))
        reg.register_node_rule(py_only)
        py_table = reg.build_dispatch_table("python")
        js_table = reg.build_dispatch_table("javascript")
        assert TYPE_CALL in py_table
        assert TYPE_CALL not in js_table

    def test_file_rules(self) -> None:
        reg = RuleRegistry()
        fr = _MockFileRule()
        reg.register_file_rule(fr)
        assert len(reg.get_file_rules("python")) == 1

    def test_file_rules_language_filter(self) -> None:
        reg = RuleRegistry()
        fr = _MockFileRule(frozenset({"javascript"}))
        reg.register_file_rule(fr)
        assert len(reg.get_file_rules("python")) == 0
        assert len(reg.get_file_rules("javascript")) == 1


class TestEvaluateFile:
    def test_finds_matching_nodes(self) -> None:
        from airev_core.parsers.python_parser import PythonParser

        parser = PythonParser()
        arena = parser.parse(b"foo()")
        ctx = _make_ctx(arena)
        rule = _MockNodeRule(frozenset({TYPE_CALL}))
        findings = evaluate_file(arena, {TYPE_CALL: [rule]}, [], ctx)
        assert len(findings) >= 1

    def test_empty_dispatch_table(self) -> None:
        arena = UastArena(capacity=10)
        arena.allocate(TYPE_CALL, 0, 5, 1, 0)
        ctx = _make_ctx(arena)
        findings = evaluate_file(arena, {}, [], ctx)
        assert findings == []

    def test_file_rules_run(self) -> None:
        arena = UastArena(capacity=10)
        ctx = _make_ctx(arena)
        fr = _MockFileRule()
        findings = evaluate_file(arena, {}, [fr], ctx)
        assert len(findings) == 1
        assert findings[0].rule_id == "file-finding"

    def test_pure_function(self) -> None:
        arena = UastArena(capacity=10)
        arena.allocate(TYPE_CALL, 0, 5, 1, 0, name="foo")
        ctx = _make_ctx(arena)
        rule = _MockNodeRule(frozenset({TYPE_CALL}))
        r1 = evaluate_file(arena, {TYPE_CALL: [rule]}, [], ctx)
        rule2 = _MockNodeRule(frozenset({TYPE_CALL}))
        r2 = evaluate_file(arena, {TYPE_CALL: [rule2]}, [], ctx)
        assert len(r1) == len(r2)
        assert r1[0].rule_id == r2[0].rule_id
