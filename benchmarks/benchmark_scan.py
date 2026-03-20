#!/usr/bin/env python3
"""Performance benchmark for airev scan pipeline.

Generates a synthetic project with configurable size and measures
parse, analysis, and total scan time.

Usage:
    python benchmarks/benchmark_scan.py
    python benchmarks/benchmark_scan.py --files 500 --loc 200
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Ensure project root is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_PYTHON_TEMPLATE = '''\
"""Auto-generated benchmark file {n}."""

import os
import sys
import json
from pathlib import Path


def process_data_{n}(items: list[str]) -> dict[str, int]:
    """Process a list of items."""
    result: dict[str, int] = {{}}
    for item in items:
        result[item] = len(item)
    return result


def helper_{n}(value: str) -> str:
    """Helper function."""
    return value.strip().lower()


class Handler_{n}:
    """A handler class."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self) -> None:
        data = process_data_{n}([self.name])
        print(data)
'''

_JS_TEMPLATE = """\
// Auto-generated benchmark file {n}

const fs = require('fs');
const path = require('path');

function processData{n}(items) {{
    const result = {{}};
    for (const item of items) {{
        result[item] = item.length;
    }}
    return result;
}}

function helper{n}(value) {{
    return value.trim().toLowerCase();
}}

class Handler{n} {{
    constructor(name) {{
        this.name = name;
    }}

    run() {{
        const data = processData{n}([this.name]);
        console.log(data);
    }}
}}

module.exports = {{ processData{n}, helper{n}, Handler{n} }};
"""


def generate_project(root: Path, num_files: int = 100, mix_ratio: float = 0.7) -> None:
    """Generate a synthetic project with Python and JS files."""
    py_count = int(num_files * mix_ratio)
    js_count = num_files - py_count

    src = root / "src"
    src.mkdir(exist_ok=True)

    for i in range(py_count):
        (src / f"module_{i}.py").write_text(_PYTHON_TEMPLATE.format(n=i), encoding="utf-8")

    js_dir = src / "js"
    js_dir.mkdir(exist_ok=True)
    for i in range(js_count):
        (js_dir / f"component_{i}.js").write_text(_JS_TEMPLATE.format(n=i), encoding="utf-8")


def run_benchmark(num_files: int = 100) -> None:
    """Run the benchmark and print results."""
    tmpdir = tempfile.mkdtemp(prefix="airev_bench_")
    try:
        root = Path(tmpdir)
        print(f"Generating {num_files} files...")
        t0 = time.perf_counter()
        generate_project(root, num_files)
        gen_time = time.perf_counter() - t0
        print(f"  Generated in {gen_time:.2f}s\n")

        # Count actual files
        py_files = list(root.rglob("*.py"))
        js_files = list(root.rglob("*.js"))
        total_bytes = sum(f.stat().st_size for f in py_files + js_files)

        print(f"Project: {len(py_files)} Python + {len(js_files)} JS files")
        print(f"Total size: {total_bytes / 1024:.1f} KB\n")

        # Import here to measure fresh import time
        t_import = time.perf_counter()
        from airev_core.parsers import ParserRegistry
        from airev_core.rules.common.deprecated_api import DeprecatedApiRule
        from airev_core.rules.common.hallucinated_api import HallucinatedApiRule
        from airev_core.rules.common.hardcoded_secrets import HardcodedSecretsRule
        from airev_core.rules.common.phantom_import import PhantomImportRule
        from airev_core.rules.common.reinvented_internal import ReinventedInternalRule
        from airev_core.rules.registry import RuleRegistry, evaluate_file
        from airev_core.semantics.builder import SemanticBuilder
        from airev_core.semantics.context import LintContext
        from airev_core.semantics.resolver import ImportResolver

        import_time = time.perf_counter() - t_import

        # Setup
        parser_reg = ParserRegistry()
        rule_reg = RuleRegistry()
        for rule in [PhantomImportRule(), HallucinatedApiRule(), DeprecatedApiRule()]:
            rule_reg.register_node_rule(rule)
        for rule in [HardcodedSecretsRule(), ReinventedInternalRule()]:
            rule_reg.register_file_rule(rule)
        builder = SemanticBuilder()

        # Phase 1: Parse
        t_parse = time.perf_counter()
        parsed = []
        total_nodes = 0
        for fpath in py_files + js_files:
            lang = parser_reg.get_language(str(fpath))
            if lang is None:
                continue
            parser = parser_reg.get_parser(str(fpath))
            if parser is None:
                continue
            source = fpath.read_bytes()
            arena = parser.parse(source)
            semantic = builder.build(arena, lang)
            total_nodes += arena.count
            parsed.append((fpath, lang, arena, semantic, source))
        parse_time = time.perf_counter() - t_parse

        # Phase 2: Evaluate
        t_eval = time.perf_counter()
        total_findings = 0
        for fpath, lang, arena, semantic, source in parsed:
            resolver = ImportResolver(str(root), lang)
            ctx = LintContext(
                arena=arena,
                semantic=semantic,
                file_path=str(fpath),
                language=lang,
                source=source,
                resolver=resolver,
            )
            dispatch = rule_reg.build_dispatch_table(lang)
            file_rules = rule_reg.get_file_rules(lang)
            findings = evaluate_file(arena, dispatch, file_rules, ctx)
            total_findings += len(findings)
        eval_time = time.perf_counter() - t_eval

        total_time = parse_time + eval_time

        # Print results
        print("=" * 50)
        print("BENCHMARK RESULTS")
        print("=" * 50)
        print(f"  Files:       {len(parsed)}")
        print(f"  AST nodes:   {total_nodes:,}")
        print(f"  Findings:    {total_findings}")
        print(f"  Import time: {import_time:.3f}s")
        print(f"  Parse time:  {parse_time:.3f}s")
        print(f"  Eval time:   {eval_time:.3f}s")
        print(f"  Total time:  {total_time:.3f}s")
        print(f"  Throughput:  {len(parsed) / total_time:.0f} files/s")
        print(f"  Node rate:   {total_nodes / total_time:,.0f} nodes/s")
        print("=" * 50)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="airev performance benchmark")
    parser.add_argument("--files", type=int, default=100, help="Number of files to generate")
    args = parser.parse_args()
    run_benchmark(args.files)


if __name__ == "__main__":
    main()
