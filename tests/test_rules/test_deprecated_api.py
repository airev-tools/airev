"""Tests for the deprecated-api detection rule."""

from __future__ import annotations

import pickle
from pathlib import Path

from airev_core.findings.models import Severity
from airev_core.parsers.python_parser import PythonParser
from airev_core.parsers.typescript_parser import TypeScriptParser
from airev_core.rules.common.deprecated_api import DeprecatedApiRule
from airev_core.rules.common.deprecation_db import DEPRECATED_APIS, DeprecatedAPI
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
    rule = DeprecatedApiRule()
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
    rule = DeprecatedApiRule()
    reg = RuleRegistry()
    reg.register_node_rule(rule)
    table = reg.build_dispatch_table("typescript")
    return evaluate_file(arena, table, [], ctx)


class TestDeprecatedApiPython:
    """True positive tests — deprecated Python APIs."""

    def test_os_popen(self, tmp_path: Path) -> None:
        source = b'import os\nos.popen("ls")\n'
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) >= 1
        assert any("os.popen" in f.message for f in findings)  # type: ignore[union-attr]
        assert any("subprocess.run()" in f.message for f in findings)  # type: ignore[union-attr]

    def test_typing_optional(self, tmp_path: Path) -> None:
        source = b"from typing import Optional\n"
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) >= 1
        assert any("Optional" in f.message for f in findings)  # type: ignore[union-attr]

    def test_typing_list(self, tmp_path: Path) -> None:
        source = b"from typing import List\n"
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) >= 1
        assert any("List" in f.message for f in findings)  # type: ignore[union-attr]

    def test_bad_deprecated_fixture(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "deprecated_api" / "bad_deprecated.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) >= 2  # os.popen + typing imports

    def test_replacement_in_message(self, tmp_path: Path) -> None:
        source = b"from typing import Optional\n"
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) >= 1
        msg = findings[0].message  # type: ignore[union-attr]
        assert "X | None" in msg


class TestDeprecatedApiTypeScript:
    """True positive tests — deprecated JS/TS APIs."""

    def test_url_parse(self, tmp_path: Path) -> None:
        source = b'import url from "url";\nconst p = url.parse("http://x.com");\n'
        findings = _run_rule_ts(source, tmp_path)
        assert len(findings) >= 1
        assert any("url.parse" in f.message for f in findings)  # type: ignore[union-attr]

    def test_crypto_create_cipher(self, tmp_path: Path) -> None:
        source = b'import crypto from "crypto";\ncrypto.createCipher("aes", "k");\n'
        findings = _run_rule_ts(source, tmp_path)
        assert len(findings) >= 1
        assert any("createCipher" in f.message for f in findings)  # type: ignore[union-attr]


class TestDeprecatedApiFalsePositives:
    """True negative tests — modern APIs should NOT flag."""

    def test_good_modern_python(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "deprecated_api" / "good_modern.py").read_bytes()
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) == 0

    def test_good_modern_ts(self, tmp_path: Path) -> None:
        source = (FIXTURES / "typescript" / "deprecated_api" / "good_modern.ts").read_bytes()
        findings = _run_rule_ts(source, tmp_path)
        assert len(findings) == 0

    def test_collections_ordereddict_not_flagged(self, tmp_path: Path) -> None:
        source = b"from collections import OrderedDict\n"
        findings = _run_rule_python(source, tmp_path)
        assert len(findings) == 0


class TestDeprecatedApiSnapshot:
    def test_snapshot(self, tmp_path: Path, snapshot) -> None:  # type: ignore[no-untyped-def]
        source = b"import os\nfrom typing import Optional, List\nos.popen('ls')\n"
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


class TestDeprecationDb:
    def test_deprecated_api_is_frozen(self) -> None:
        entry = DEPRECATED_APIS[0]
        assert isinstance(entry, DeprecatedAPI)

    def test_severity_values(self) -> None:
        for entry in DEPRECATED_APIS:
            assert entry.severity in (Severity.ERROR, Severity.WARNING)

    def test_pickle_roundtrip(self) -> None:
        entry = DEPRECATED_APIS[0]
        data = pickle.dumps(entry)
        restored = pickle.loads(data)  # noqa: S301
        assert restored == entry

    def test_rule_pickle(self) -> None:
        rule = DeprecatedApiRule()
        data = pickle.dumps(rule)
        restored = pickle.loads(data)  # noqa: S301
        assert restored.id == "deprecated-api"
