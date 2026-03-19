"""Comprehensive JS/TS edge case tests for phantom-import rule."""

from pathlib import Path

import pytest

from airev_core.parsers.typescript_parser import TypeScriptParser
from airev_core.rules.common.phantom_import import PhantomImportRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext
from airev_core.semantics.resolver import ImportResolver


def _run(source: bytes, tmp_path: Path) -> list[object]:
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


class TestPhantomImportJsEdges:
    def test_dynamic_import_await(self, tmp_path: Path) -> None:
        """await import('...') is not a static import — should NOT flag."""
        source = b'const mod = await import("nonexistent-pkg");\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_commonjs_require(self, tmp_path: Path) -> None:
        """require('...') is not a static import — should NOT flag."""
        source = b'const mod = require("nonexistent-pkg");\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_node_protocol_prefix(self, tmp_path: Path) -> None:
        """node: protocol prefix imports should NOT flag."""
        source = b'import fs from "node:fs";\nimport path from "node:path";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_relative_imports_with_extension(self, tmp_path: Path) -> None:
        """Relative imports should NOT flag."""
        source = b'import { helper } from "./utils";\nimport config from "../config";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_relative_imports_without_extension(self, tmp_path: Path) -> None:
        """Relative imports without extension should NOT flag."""
        source = b'import { helper } from "./utils/index";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    @pytest.mark.xfail(strict=True, reason="TypeScript type-only imports not yet distinguished")
    def test_type_only_import(self, tmp_path: Path) -> None:
        """import type { X } should NOT flag (type-only)."""
        source = b'import type { MyType } from "nonexistent-pkg";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    @pytest.mark.xfail(strict=True, reason="Side-effect imports not yet tracked")
    def test_side_effect_import(self, tmp_path: Path) -> None:
        """import 'reflect-metadata' (side-effect only) should NOT flag."""
        source = b'import "reflect-metadata";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_builtin_node_modules(self, tmp_path: Path) -> None:
        """Built-in Node modules should NOT flag."""
        source = b'import fs from "fs";\nimport path from "path";\nimport http from "http";\n'
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_scoped_package_not_crash(self, tmp_path: Path) -> None:
        """Scoped packages should not crash — may or may not flag depending on install."""
        source = b'import pkg from "@company/internal-package";\n'
        findings = _run(source, tmp_path)
        assert isinstance(findings, list)
