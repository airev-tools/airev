"""Tests for the phantom-import detection rule."""

from __future__ import annotations

from pathlib import Path

from airev_core.parsers.python_parser import PythonParser
from airev_core.parsers.typescript_parser import TypeScriptParser
from airev_core.rules.common.phantom_import import PhantomImportRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext
from airev_core.semantics.resolver import ImportResolver

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _run_rule_python(source: bytes, tmp_path: Path) -> list[object]:
    parser = PythonParser()
    arena = parser.parse(source)
    builder = SemanticBuilder()
    semantic = builder.build(arena, "python")
    resolver = ImportResolver(str(tmp_path), "python")
    ctx = LintContext(
        arena=arena,
        semantic=semantic,
        file_path="test.py",
        language="python",
        source=source,
        resolver=resolver,
    )
    rule = PhantomImportRule()
    reg = RuleRegistry()
    reg.register_node_rule(rule)
    table = reg.build_dispatch_table("python")
    return evaluate_file(arena, table, [], ctx)


def _run_rule_ts(source: bytes, tmp_path: Path) -> list[object]:
    parser = TypeScriptParser()
    arena = parser.parse(source)
    builder = SemanticBuilder()
    semantic = builder.build(arena, "typescript")
    resolver = ImportResolver(str(tmp_path), "typescript")
    ctx = LintContext(
        arena=arena,
        semantic=semantic,
        file_path="test.ts",
        language="typescript",
        source=source,
        resolver=resolver,
    )
    rule = PhantomImportRule()
    reg = RuleRegistry()
    reg.register_node_rule(rule)
    table = reg.build_dispatch_table("typescript")
    return evaluate_file(arena, table, [], ctx)


class TestPhantomImportPython:
    def test_bad_nonexistent_package(self, tmp_path: Path) -> None:
        source = (
            FIXTURES / "python" / "phantom_import" / "bad_nonexistent_package.py"
        ).read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) == 2
        assert all(f.rule_id == "phantom-import" for f in findings)  # type: ignore[union-attr]

    def test_bad_typo_package(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "phantom_import" / "bad_typo_package.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) == 2

    def test_good_stdlib(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "phantom_import" / "good_stdlib.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) == 0

    def test_good_relative(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "phantom_import" / "good_relative.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) == 0

    def test_finding_contains_module_name(self, tmp_path: Path) -> None:
        findings = _run_rule_python(b"import crypto_secure_hash", tmp_path)
        assert len(findings) == 1
        assert "crypto_secure_hash" in findings[0].message  # type: ignore[union-attr]

    def test_finding_has_correct_line(self, tmp_path: Path) -> None:
        findings = _run_rule_python(b"import crypto_secure_hash", tmp_path)
        assert len(findings) == 1
        assert findings[0].span.start_line == 1  # type: ignore[union-attr]

    def test_snapshot(self, tmp_path: Path, snapshot) -> None:  # type: ignore[no-untyped-def]
        source = (
            FIXTURES / "python" / "phantom_import" / "bad_nonexistent_package.py"
        ).read_bytes()
        findings = _run_rule_python(source, tmp_path)
        state = [
            {
                "rule_id": f.rule_id,  # type: ignore[union-attr]
                "message": f.message,  # type: ignore[union-attr]
                "severity": f.severity,  # type: ignore[union-attr]
                "line": f.span.start_line,  # type: ignore[union-attr]
            }
            for f in findings
        ]
        assert state == snapshot


class TestPhantomImportTypeScript:
    def test_bad_nonexistent_package(self, tmp_path: Path) -> None:
        source = (
            FIXTURES / "typescript" / "phantom_import" / "bad_nonexistent_package.ts"
        ).read_bytes()
        findings = _run_rule_ts(source, tmp_path)
        assert len(findings) == 2
        assert all(f.rule_id == "phantom-import" for f in findings)  # type: ignore[union-attr]

    def test_good_builtins(self, tmp_path: Path) -> None:
        source = (FIXTURES / "typescript" / "phantom_import" / "good_builtins.ts").read_bytes()
        findings = _run_rule_ts(source, tmp_path)
        assert len(findings) == 0
