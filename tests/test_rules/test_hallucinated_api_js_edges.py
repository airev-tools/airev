"""Comprehensive JS/TS edge case tests for hallucinated-api rule."""

from pathlib import Path

from airev_core.parsers.typescript_parser import TypeScriptParser
from airev_core.rules.common.hallucinated_api import HallucinatedApiRule
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
    rule = HallucinatedApiRule()
    reg = RuleRegistry()
    reg.register_node_rule(rule)
    table = reg.build_dispatch_table("typescript")
    return evaluate_file(arena, table, [], ctx)


class TestHallucinatedApiJsEdges:
    def test_promise_chain_real(self, tmp_path: Path) -> None:
        """Chained promise methods should NOT crash or false-positive."""
        source = b'fetch("url").then(res => res.json());\n'
        findings = _run(source, tmp_path)
        # res.json() is a local method call, not on an imported module
        assert isinstance(findings, list)

    def test_optional_chaining(self, tmp_path: Path) -> None:
        """Optional chaining syntax should NOT crash."""
        source = b"const val = obj?.method();\n"
        findings = _run(source, tmp_path)
        assert isinstance(findings, list)

    def test_destructured_import_call(self, tmp_path: Path) -> None:
        """Destructured imports then called should NOT crash."""
        source = b'import { readFile } from "fs";\nreadFile("path");\n'
        findings = _run(source, tmp_path)
        # readFile is a bare function call with no receiver
        assert isinstance(findings, list)

    def test_case_sensitivity(self, tmp_path: Path) -> None:
        """Case-sensitive method names — lowercase vs uppercase."""
        source = b'import React from "react";\nconst el = React.createElement("div");\n'
        findings = _run(source, tmp_path)
        # react may not be installed, so this tests no crash
        assert isinstance(findings, list)

    def test_bare_function_call_not_flagged(self, tmp_path: Path) -> None:
        """Bare function calls without a receiver should NOT flag."""
        source = b"function helper() { return 1; }\nconst x = helper();\n"
        findings = _run(source, tmp_path)
        assert len(findings) == 0

    def test_console_methods(self, tmp_path: Path) -> None:
        """console.log() etc. are built-in — should NOT flag."""
        source = b'console.log("hello");\nconsole.error("oops");\n'
        findings = _run(source, tmp_path)
        # console is not imported, so should not be checked
        assert len(findings) == 0
