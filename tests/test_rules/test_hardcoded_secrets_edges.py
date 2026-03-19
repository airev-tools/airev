"""Comprehensive Python edge case tests for hardcoded-secrets rule."""

from pathlib import Path

from airev_core.parsers.python_parser import PythonParser
from airev_core.rules.common.hardcoded_secrets import HardcodedSecretsRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext
from airev_core.semantics.resolver import ImportResolver


def _run(source: bytes, tmp_path: Path, file_path: str = "app.py") -> list[object]:
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


class TestHardcodedSecretsEdges:
    def test_base64_png_not_flagged(self, tmp_path: Path) -> None:
        """Base64-encoded PNG data should NOT flag."""
        source = b'icon = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_sha256_hash_not_flagged(self, tmp_path: Path) -> None:
        """Known SHA256 hash constants should NOT flag."""
        source = (
            b'EMPTY_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"\n'
        )
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_fstring_with_variable_not_flagged(self, tmp_path: Path) -> None:
        """F-strings with variable references should NOT flag."""
        source = b'token = f"Bearer {get_token()}"\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_empty_string_assignment_not_flagged(self, tmp_path: Path) -> None:
        """Empty string assigned to secret var should NOT flag."""
        source = b'api_key = ""\nsecret = ""\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_secrets_in_comments_not_flagged(self, tmp_path: Path) -> None:
        """Secrets in comments should NOT flag (we scan code, not comments)."""
        source = b'# password = "SuperSecret123!"\n# api_key = "AKIATESTFAKEKEY12345X"\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_uuid_constant_not_flagged(self, tmp_path: Path) -> None:
        """UUID constants should NOT flag (not secrets)."""
        source = b'REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000"\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_test_file_py_prefix(self, tmp_path: Path) -> None:
        """test_*.py files should NOT flag."""
        source = b'password = "real_secret_here"\n'
        findings = _run(source, tmp_path, file_path="test_auth.py")
        assert len(findings) == 0

    def test_test_file_py_suffix(self, tmp_path: Path) -> None:
        """*_test.py files should NOT flag."""
        source = b'password = "real_secret_here"\n'
        findings = _run(source, tmp_path, file_path="auth_test.py")
        assert len(findings) == 0

    def test_js_comment_not_flagged(self, tmp_path: Path) -> None:
        """JS-style comments should NOT flag."""
        source = b'// const apiKey = "abc123def456ghi789jkl012mno345pqr";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_none_assignment_not_flagged(self, tmp_path: Path) -> None:
        """None assignment to secret var should NOT flag."""
        source = b"api_key = None\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0
