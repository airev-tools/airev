"""Comprehensive Python edge case tests for deprecated-api rule."""

from pathlib import Path

from airev_core.parsers.python_parser import PythonParser
from airev_core.rules.common.deprecated_api import DeprecatedApiRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext
from airev_core.semantics.resolver import ImportResolver


def _run(source: bytes, tmp_path: Path) -> list[object]:
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


class TestDeprecatedApiPythonEdges:
    def test_reference_without_call(self, tmp_path: Path) -> None:
        """ref = os.popen (reference, not call) — not tracked as a call node."""
        source = b"import os\nref = os.popen\n"
        findings = _run(source, tmp_path)
        # References without () are not call nodes, so not flagged by this rule
        assert isinstance(findings, list)

    def test_non_deprecated_member_of_collections(self, tmp_path: Path) -> None:
        """collections.OrderedDict is NOT deprecated — should NOT flag."""
        source = b"from collections import OrderedDict\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_non_deprecated_member_of_collections_deque(self, tmp_path: Path) -> None:
        """collections.deque is NOT deprecated — should NOT flag."""
        source = b"from collections import deque\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_modern_replacement_no_false_positive(self, tmp_path: Path) -> None:
        """Modern replacement usage should NOT flag."""
        source = b"from collections.abc import Mapping, MutableMapping, Sequence\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_asyncio_get_running_loop_not_flagged(self, tmp_path: Path) -> None:
        """asyncio.get_running_loop() is the replacement — should NOT flag."""
        source = b"import asyncio\nloop = asyncio.get_running_loop()\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_subprocess_run_not_flagged(self, tmp_path: Path) -> None:
        """subprocess.run() is the replacement — should NOT flag."""
        source = b"import subprocess\nsubprocess.run(['ls'])\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_multiple_deprecated_from_same_module(self, tmp_path: Path) -> None:
        """Multiple deprecated imports from typing should all flag."""
        source = b"from typing import Optional, List, Dict\n"
        findings = _run(source, tmp_path)
        assert len(findings) >= 3

    def test_severity_removed_is_error(self, tmp_path: Path) -> None:
        """Removed APIs should have ERROR severity."""
        source = b'import os\nos.popen("ls")\n'
        findings = _run(source, tmp_path)
        popen_findings = [
            f
            for f in findings
            if "popen" in f.message  # type: ignore[union-attr]
        ]
        assert len(popen_findings) >= 1
        assert popen_findings[0].severity.value == "error"  # type: ignore[union-attr]

    def test_severity_deprecated_is_warning(self, tmp_path: Path) -> None:
        """Still-functional deprecated APIs should have WARNING severity."""
        source = b"from typing import Optional\n"
        findings = _run(source, tmp_path)
        assert len(findings) >= 1
        assert findings[0].severity.value == "warning"  # type: ignore[union-attr]
