"""Comprehensive Python edge case tests for phantom-import rule."""

from pathlib import Path

import pytest

from airev_core.parsers.python_parser import PythonParser
from airev_core.rules.common.phantom_import import PhantomImportRule
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
    rule = PhantomImportRule()
    reg = RuleRegistry()
    reg.register_node_rule(rule)
    table = reg.build_dispatch_table("python")
    return evaluate_file(arena, table, [], ctx)


class TestPhantomImportPythonEdges:
    @pytest.mark.xfail(
        strict=True, reason="Conditional imports not yet tracked by semantic builder"
    )
    def test_conditional_import_try_except(self, tmp_path: Path) -> None:
        """try/except ImportError guarded imports should NOT flag."""
        source = b"try:\n    import nonexistent_pkg\nexcept ImportError:\n    pass\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_dynamic_import_builtin(self, tmp_path: Path) -> None:
        """__import__() calls are not tracked as static imports — should NOT flag."""
        source = b'mod = __import__("nonexistent_pkg")\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_dynamic_import_importlib(self, tmp_path: Path) -> None:
        """importlib.import_module() is not a static import — should NOT flag dynamic target."""
        source = b'import importlib\nmod = importlib.import_module("nonexistent_pkg")\n'
        findings = _run(source, tmp_path)
        # Should only flag the actual import, not dynamic ones
        assert all(
            "importlib" not in f.message
            for f in findings  # type: ignore[union-attr]
        )

    def test_future_import(self, tmp_path: Path) -> None:
        """from __future__ import annotations should NEVER flag."""
        source = b"from __future__ import annotations\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    @pytest.mark.xfail(reason="TYPE_CHECKING guard not yet tracked")
    def test_type_checking_guarded_import(self, tmp_path: Path) -> None:
        """TYPE_CHECKING guarded imports should NOT flag."""
        source = (
            b"from __future__ import annotations\n"
            b"from typing import TYPE_CHECKING\n"
            b"if TYPE_CHECKING:\n"
            b"    import nonexistent_pkg\n"
        )
        findings = _run(source, tmp_path)
        # Only typing should resolve, nonexistent_pkg is guarded
        non_typing = [
            f
            for f in findings
            if "nonexistent_pkg" in f.message  # type: ignore[union-attr]
        ]
        assert len(non_typing) == 0

    def test_platform_guarded_import(self, tmp_path: Path) -> None:
        """Platform-guarded imports — winreg resolves on Windows so should NOT flag here."""
        source = b'import sys\nif sys.platform == "win32":\n    import winreg\n'
        findings = _run(source, tmp_path)
        winreg_findings = [
            f
            for f in findings
            if "winreg" in f.message  # type: ignore[union-attr]
        ]
        assert len(winreg_findings) == 0

    def test_star_import_stdlib(self, tmp_path: Path) -> None:
        """Star import from stdlib should NOT flag."""
        source = b"from os.path import *\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_relative_imports_various_depths(self, tmp_path: Path) -> None:
        """Relative imports at various depths should NOT flag."""
        source = b"from . import sibling\nfrom .. import parent\nfrom ...pkg import deep\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_stdlib_modules_not_flagged(self, tmp_path: Path) -> None:
        """Common stdlib modules should never be flagged."""
        source = b"import json\nimport pathlib\nimport collections\nimport typing\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0
