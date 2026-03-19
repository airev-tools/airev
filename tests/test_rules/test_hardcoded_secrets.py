"""Tests for the hardcoded-secrets detection rule."""

from __future__ import annotations

import pickle
from pathlib import Path

from airev_core.parsers.python_parser import PythonParser
from airev_core.parsers.typescript_parser import TypeScriptParser
from airev_core.rules.common.hardcoded_secrets import HardcodedSecretsRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext
from airev_core.semantics.resolver import ImportResolver

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _run_rule_python(
    source: bytes,
    tmp_path: Path,
    file_path: str = "app.py",
) -> list[object]:
    parser = PythonParser()
    arena = parser.parse(source)
    builder = SemanticBuilder()
    semantic = builder.build(arena, "python")
    resolver = ImportResolver(str(tmp_path), "python")
    ctx = LintContext(
        arena=arena,
        semantic=semantic,
        file_path=file_path,
        language="python",
        source=source,
        resolver=resolver,
    )
    rule = HardcodedSecretsRule()
    reg = RuleRegistry()
    reg.register_file_rule(rule)
    table = reg.build_dispatch_table("python")
    file_rules = reg.get_file_rules("python")
    return evaluate_file(arena, table, file_rules, ctx)


def _run_rule_ts(
    source: bytes,
    tmp_path: Path,
    file_path: str = "app.ts",
) -> list[object]:
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


class TestHardcodedSecretsPython:
    """True positive tests — code that SHOULD trigger the rule."""

    def test_bad_aws_key(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "hardcoded_secrets" / "bad_aws_key.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) >= 2
        messages = [f.message for f in findings]  # type: ignore[union-attr]
        assert any("AWS" in m for m in messages)

    def test_bad_generic_secrets(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "hardcoded_secrets" / "bad_generic_secrets.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) >= 2
        messages = [f.message for f in findings]  # type: ignore[union-attr]
        assert any("password" in m.lower() or "Database" in m for m in messages)

    def test_bad_high_entropy(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "hardcoded_secrets" / "bad_high_entropy.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) >= 1

    def test_finding_has_correct_rule_id(self, tmp_path: Path) -> None:
        findings = _run_rule_python(b'password = "hunter2_secret"', tmp_path)
        assert len(findings) >= 1
        assert all(
            f.rule_id == "hardcoded-secrets"
            for f in findings  # type: ignore[union-attr]
        )

    def test_finding_has_line_number(self, tmp_path: Path) -> None:
        findings = _run_rule_python(b'password = "hunter2_secret"', tmp_path)
        assert len(findings) >= 1
        assert findings[0].span.start_line == 1  # type: ignore[union-attr]


class TestHardcodedSecretsTypeScript:
    """True positive tests for TypeScript."""

    def test_bad_secrets_ts(self, tmp_path: Path) -> None:
        source = (FIXTURES / "typescript" / "hardcoded_secrets" / "bad_secrets.ts").read_bytes()
        findings = _run_rule_ts(source, tmp_path)
        assert len(findings) >= 1
        messages = [f.message for f in findings]  # type: ignore[union-attr]
        assert any("Database" in m for m in messages)


class TestHardcodedSecretsFalsePositives:
    """True negative tests — code that should NOT trigger the rule."""

    def test_good_placeholders(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "hardcoded_secrets" / "good_placeholders.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) == 0

    def test_good_env_vars(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "hardcoded_secrets" / "good_env_vars.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) == 0

    def test_good_test_file(self, tmp_path: Path) -> None:
        """Secrets in test files should be suppressed."""
        source = (FIXTURES / "python" / "hardcoded_secrets" / "good_test_secrets.py").read_bytes()
        findings = _run_rule_python(source, tmp_path, file_path="test_example.py")
        assert len(findings) == 0

    def test_good_env_vars_ts(self, tmp_path: Path) -> None:
        source = (FIXTURES / "typescript" / "hardcoded_secrets" / "good_env_vars.ts").read_bytes()
        findings = _run_rule_ts(source, tmp_path)
        assert len(findings) == 0

    def test_empty_string_not_flagged(self, tmp_path: Path) -> None:
        findings = _run_rule_python(b'password = ""', tmp_path)
        assert len(findings) == 0

    def test_comment_not_flagged(self, tmp_path: Path) -> None:
        findings = _run_rule_python(b'# password = "hunter2_secret"', tmp_path)
        assert len(findings) == 0


class TestHardcodedSecretsSnapshot:
    def test_snapshot(self, tmp_path: Path, snapshot) -> None:  # type: ignore[no-untyped-def]
        source = (FIXTURES / "python" / "hardcoded_secrets" / "bad_aws_key.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        state = [
            {
                "rule_id": f.rule_id,  # type: ignore[union-attr]
                "message": f.message,  # type: ignore[union-attr]
                "severity": str(f.severity),  # type: ignore[union-attr]
                "line": f.span.start_line,  # type: ignore[union-attr]
            }
            for f in findings
        ]
        assert state == snapshot


class TestHardcodedSecretsPickle:
    def test_rule_pickle_roundtrip(self) -> None:
        rule = HardcodedSecretsRule()
        data = pickle.dumps(rule)
        restored = pickle.loads(data)  # noqa: S301
        assert restored.id == "hardcoded-secrets"
