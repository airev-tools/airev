"""Tests for LintContext."""

from __future__ import annotations

import dataclasses

import pytest

from airev_core.parsers.python_parser import PythonParser
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext


class _StubResolver:
    """Minimal resolver stub for testing."""

    def module_exists(self, module_name: str) -> bool:
        return True


class TestLintContext:
    def test_all_fields_accessible(self) -> None:
        source = b"import os\nos.listdir('.')"
        parser = PythonParser()
        arena = parser.parse(source)
        builder = SemanticBuilder()
        semantic = builder.build(arena, "python")
        resolver = _StubResolver()

        ctx = LintContext(
            arena=arena,
            semantic=semantic,
            file_path="test.py",
            language="python",
            source=source,
            resolver=resolver,  # type: ignore[arg-type]
        )

        assert ctx.file_path == "test.py"
        assert ctx.language == "python"
        assert ctx.source == source
        assert ctx.arena is arena
        assert ctx.semantic is semantic
        assert ctx.resolver is resolver

    def test_immutable(self) -> None:
        source = b"import os"
        parser = PythonParser()
        arena = parser.parse(source)
        builder = SemanticBuilder()
        semantic = builder.build(arena, "python")
        resolver = _StubResolver()

        ctx = LintContext(
            arena=arena,
            semantic=semantic,
            file_path="test.py",
            language="python",
            source=source,
            resolver=resolver,  # type: ignore[arg-type]
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.file_path = "other.py"  # type: ignore[misc]
