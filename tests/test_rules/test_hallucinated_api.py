"""Tests for the hallucinated-api detection rule."""

from __future__ import annotations

from pathlib import Path

from airev_core.parsers.python_parser import PythonParser
from airev_core.rules.common.hallucinated_api import _EXPORT_CACHE, HallucinatedApiRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext
from airev_core.semantics.resolver import ImportResolver

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _run_rule(source: bytes, tmp_path: Path) -> list[object]:
    # Clear the export cache between tests to avoid cross-contamination
    _EXPORT_CACHE.clear()

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
    rule = HallucinatedApiRule()
    reg = RuleRegistry()
    reg.register_node_rule(rule)
    table = reg.build_dispatch_table("python")
    return evaluate_file(arena, table, [], ctx)


class TestHallucinatedApi:
    def test_bad_os_method(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "hallucinated_api" / "bad_os_method.py").read_bytes()
        findings = _run_rule(source, tmp_path)
        assert len(findings) == 1
        assert findings[0].rule_id == "hallucinated-api"  # type: ignore[union-attr]
        assert "list_directory" in findings[0].message  # type: ignore[union-attr]

    def test_good_os(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "hallucinated_api" / "good_os.py").read_bytes()
        findings = _run_rule(source, tmp_path)
        assert len(findings) == 0

    def test_edge_dynamic_attr(self, tmp_path: Path) -> None:
        source = (FIXTURES / "python" / "hallucinated_api" / "edge_dynamic_attr.py").read_bytes()
        findings = _run_rule(source, tmp_path)
        # getattr(json, "loads") is not a json.loads() call — should not flag
        assert len(findings) == 0

    def test_no_receiver_no_finding(self, tmp_path: Path) -> None:
        # Plain function calls without receiver should not trigger
        findings = _run_rule(b"foo()", tmp_path)
        assert len(findings) == 0

    def test_finding_message_names_method(self, tmp_path: Path) -> None:
        findings = _run_rule(b"import os\nos.list_directory('.')", tmp_path)
        assert len(findings) == 1
        assert "list_directory" in findings[0].message  # type: ignore[union-attr]
        assert "os" in findings[0].message  # type: ignore[union-attr]

    def test_unresolvable_module_skipped(self, tmp_path: Path) -> None:
        # If the module is not installed, the rule should skip (not false-positive)
        findings = _run_rule(b"import fake_module_xyz\nfake_module_xyz.method()", tmp_path)
        # The export lookup returns None for non-installed modules → skip
        assert len(findings) == 0

    def test_snapshot(self, tmp_path: Path, snapshot) -> None:  # type: ignore[no-untyped-def]
        source = (FIXTURES / "python" / "hallucinated_api" / "bad_os_method.py").read_bytes()
        findings = _run_rule(source, tmp_path)
        state = [
            {
                "rule_id": f.rule_id,  # type: ignore[union-attr]
                "message": f.message,  # type: ignore[union-attr]
                "severity": f.severity,  # type: ignore[union-attr]
                "confidence": f.confidence,  # type: ignore[union-attr]
                "line": f.span.start_line,  # type: ignore[union-attr]
            }
            for f in findings
        ]
        assert state == snapshot
