"""Comprehensive JS/TS edge case tests for hardcoded-secrets rule."""

from pathlib import Path

from airev_core.parsers.typescript_parser import TypeScriptParser
from airev_core.rules.common.hardcoded_secrets import HardcodedSecretsRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext
from airev_core.semantics.resolver import ImportResolver


def _run(source: bytes, tmp_path: Path, file_path: str = "app.ts") -> list[object]:
    parser = TypeScriptParser()
    arena = parser.parse(source)
    builder = SemanticBuilder()
    semantic = builder.build(arena, "typescript")
    resolver = ImportResolver(str(tmp_path), "typescript")
    ctx = LintContext(
        arena=arena,
        semantic=semantic,
        file_path=file_path,
        language="typescript",
        source=source,
        resolver=resolver,
    )
    rule = HardcodedSecretsRule()
    reg = RuleRegistry()
    reg.register_file_rule(rule)
    table = reg.build_dispatch_table("typescript")
    file_rules = reg.get_file_rules("typescript")
    return evaluate_file(arena, table, file_rules, ctx)


class TestHardcodedSecretsJsEdges:
    def test_template_literal_env_not_flagged(self, tmp_path: Path) -> None:
        """Template literals with process.env should NOT flag."""
        source = b"const apiKey = process.env.API_KEY;\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_top_level_secret_assignment(self, tmp_path: Path) -> None:
        """Top-level secret variable assignment SHOULD flag."""
        source = b'const password = "SuperSecretP@ssw0rd!";\n'
        findings = _run(source, tmp_path)
        assert len(findings) >= 1

    def test_process_env_fallback_not_flagged(self, tmp_path: Path) -> None:
        """process.env fallback patterns should NOT flag."""
        source = b'const token = process.env.TOKEN ?? "default";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_process_env_or_fallback(self, tmp_path: Path) -> None:
        """process.env || fallback should NOT flag."""
        source = b'const key = process.env.KEY || "fallback";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_ts_test_file_not_flagged(self, tmp_path: Path) -> None:
        """*.test.ts files should NOT flag."""
        source = b'const secret = "abc123def456ghi789jkl012mno345pqr";\n'
        findings = _run(source, tmp_path, file_path="auth.test.ts")
        assert len(findings) == 0

    def test_ts_spec_file_not_flagged(self, tmp_path: Path) -> None:
        """*.spec.ts files should NOT flag."""
        source = b'const secret = "abc123def456ghi789jkl012mno345pqr";\n'
        findings = _run(source, tmp_path, file_path="auth.spec.ts")
        assert len(findings) == 0

    def test_enum_values_not_flagged(self, tmp_path: Path) -> None:
        """TypeScript enum values should NOT flag."""
        source = b'enum Status {\n  Active = "active",\n  Inactive = "inactive",\n}\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_js_comment_not_flagged(self, tmp_path: Path) -> None:
        """JavaScript comments with secrets should NOT flag."""
        source = b'// const apiKey = "abc123def456ghi789jkl012mno345pqr";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0
