"""The `airev scan` command — walks a directory, parses files, runs rules, reports findings."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.table import Table

from airev_core.config.loader import load_config
from airev_core.discovery.ignore import IgnorePattern, is_ignored, load_ignorefile
from airev_core.findings.collector import collect
from airev_core.parsers import ParserRegistry
from airev_core.rules.common.deprecated_api import DeprecatedApiRule
from airev_core.rules.common.hallucinated_api import HallucinatedApiRule
from airev_core.rules.common.hardcoded_secrets import HardcodedSecretsRule
from airev_core.rules.common.phantom_import import PhantomImportRule
from airev_core.rules.common.reinvented_internal import ReinventedInternalRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.security.scan_policy import (
    ScanSafetyConfig,
    check_long_lines,
    evaluate_file_policy,
    safe_read_source,
)
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext, ProjectSymbols
from airev_core.semantics.resolver import ImportResolver
from airev_core.suppression import build_suppression_map, is_finding_suppressed
from airev_core.workspace.build_facts import build_workspace_facts

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.config.models import AirevConfig
    from airev_core.findings.models import Finding
    from airev_core.rules.base import FileRule, NodeRule
    from airev_core.semantics.symbols import SemanticModel

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "egg-info",
    }
)

_SEVERITY_STYLE: dict[str, str] = {
    "error": "bold red",
    "warning": "yellow",
    "info": "dim",
}


def _discover_files(
    root: Path,
    registry: ParserRegistry,
    lang_filter: str | None,
    ignore_patterns: tuple[IgnorePattern, ...] = (),
) -> list[tuple[Path, str]]:
    """Walk directory tree and return (path, language) pairs for supported files."""
    results: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _SKIP_DIRS
            and not is_ignored(
                str(Path(dirpath, d).relative_to(root)).replace("\\", "/"),
                ignore_patterns,
                is_dir=True,
            )
        ]
        for filename in filenames:
            filepath = Path(dirpath) / filename
            language = registry.get_language(str(filepath))
            if language is None:
                continue
            if lang_filter is not None and language != lang_filter:
                continue
            # Check .airevignore
            rel_path = str(filepath.relative_to(root)).replace("\\", "/")
            if is_ignored(rel_path, ignore_patterns):
                continue
            results.append((filepath, language))
    return results


def _build_registry(rule_filter: str | None, config: AirevConfig) -> RuleRegistry:
    """Create and populate the rule registry, respecting config."""
    registry = RuleRegistry()
    all_node_rules: list[NodeRule] = [
        PhantomImportRule(),
        HallucinatedApiRule(),
        DeprecatedApiRule(),
    ]
    for rule in all_node_rules:
        if rule_filter is not None and rule.id != rule_filter:
            continue
        rule_cfg = config.rules.get(rule.id)
        if rule_cfg is not None and not rule_cfg.enabled:
            continue
        registry.register_node_rule(rule)

    all_file_rules: list[FileRule] = [HardcodedSecretsRule(), ReinventedInternalRule()]
    for frule in all_file_rules:
        if rule_filter is not None and frule.id != rule_filter:
            continue
        rule_cfg = config.rules.get(frule.id)
        if rule_cfg is not None and not rule_cfg.enabled:
            continue
        registry.register_file_rule(frule)

    return registry


def _format_terminal(findings: list[Finding], root: Path, console: Console) -> None:
    """Print findings as a rich terminal table."""
    if not findings:
        return

    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Line", style="dim", justify="right")
    table.add_column("Rule", style="magenta")
    table.add_column("Severity")
    table.add_column("Message")

    for f in findings:
        try:
            rel_path = str(Path(f.file_path).relative_to(root))
        except ValueError:
            rel_path = f.file_path

        sev_style = _SEVERITY_STYLE.get(f.severity.value, "")
        table.add_row(
            rel_path,
            str(f.span.start_line),
            f.rule_id,
            f"[{sev_style}]{f.severity.value}[/{sev_style}]",
            f.message,
        )

    console.print(table)


def _format_json(findings: list[Finding]) -> None:
    """Print findings as JSON to stdout."""
    from interfaces.cli.formatters.json_fmt import format_json

    sys.stdout.write(format_json(findings) + "\n")


def _format_sarif(findings: list[Finding]) -> None:
    """Print findings as SARIF 2.1.0 to stdout."""
    from interfaces.cli.formatters.sarif import format_sarif

    sys.stdout.write(format_sarif(findings) + "\n")


@click.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--lang",
    default=None,
    help="Only scan files of this language (python, javascript, typescript)",
)
@click.option(
    "--format",
    "output_format",
    default="terminal",
    type=click.Choice(["terminal", "json", "sarif"]),
    help="Output format (default: terminal)",
)
@click.option(
    "--rule",
    "rule_filter",
    default=None,
    help="Run only this rule (e.g., phantom-import, hallucinated-api)",
)
def scan(
    path: str,
    lang: str | None,
    output_format: str,
    rule_filter: str | None,
) -> None:
    """Scan a directory for AI-generated code quality issues."""
    console = Console()
    root = Path(path).resolve()
    config = load_config(str(root))
    parser_registry = ParserRegistry()
    rule_registry = _build_registry(rule_filter, config)
    builder = SemanticBuilder()

    if output_format == "terminal":
        console.print("\n[bold]airev[/bold] v0.1.0\n")
        console.print(f"Scanning {root}...\n")

    ignore_patterns = load_ignorefile(str(root))
    # Merge config exclude patterns with .airevignore
    if config.exclude:
        from airev_core.discovery.ignore import parse_ignorefile

        config_patterns = parse_ignorefile("\n".join(config.exclude))
        ignore_patterns = ignore_patterns + config_patterns
    # Apply config language filter
    effective_lang = lang or (
        next(iter(config.languages)) if config.languages and len(config.languages) == 1 else lang
    )
    files = _discover_files(root, parser_registry, effective_lang, ignore_patterns)

    if not files:
        if output_format == "terminal":
            console.print("[dim]No supported files found.[/dim]")
            console.print("0 files scanned.\n")
        elif output_format == "json":
            sys.stdout.write("[]\n")
        elif output_format == "sarif":
            _format_sarif([])
        return

    # Phase 1: Parse all files and build semantic models
    safety_config = ScanSafetyConfig()
    parsed_files: list[tuple[Path, str, UastArena, SemanticModel, bytes]] = []
    total_nodes = 0
    total_bytes_scanned = 0
    lang_counts: dict[str, int] = {}

    for filepath, language in files:
        # Safety policy check (before parsing)
        policy = evaluate_file_policy(filepath, root, safety_config)
        if not policy.should_scan:
            continue

        # Budget check
        if len(parsed_files) >= safety_config.max_files:
            break
        if total_bytes_scanned >= safety_config.max_total_bytes:
            break

        parser = parser_registry.get_parser(str(filepath))
        if parser is None:
            continue

        source, _warning = safe_read_source(filepath)
        if not source:
            continue

        # Skip files with extremely long lines
        if check_long_lines(source, safety_config):
            continue

        total_bytes_scanned += len(source)
        arena = parser.parse(source)
        total_nodes += arena.count
        lang_counts[language] = lang_counts.get(language, 0) + 1
        semantic = builder.build(arena, language)
        parsed_files.append((filepath, language, arena, semantic, source))

    # Phase 2: Build project-wide symbol index and workspace facts
    project_symbols: ProjectSymbols = {}
    for filepath, _lang, _arena, semantic, _source in parsed_files:
        for defn in semantic.definitions:
            project_symbols.setdefault(defn.name, []).append((str(filepath), defn))

    facts = build_workspace_facts(str(root))

    # Phase 3: Evaluate rules with full context
    all_findings: list[Finding] = []

    for filepath, language, arena, semantic, source in parsed_files:
        resolver = ImportResolver(str(root), language)
        ctx = LintContext(
            arena=arena,
            semantic=semantic,
            file_path=str(filepath),
            language=language,
            source=source,
            resolver=resolver,
            project_symbols=project_symbols,
            workspace_facts=facts,
        )

        dispatch_table = rule_registry.build_dispatch_table(language)
        file_rules = rule_registry.get_file_rules(language)
        findings = evaluate_file(arena, dispatch_table, file_rules, ctx)

        # Apply inline suppression (outside rule bodies — rules stay pure)
        sup_map = build_suppression_map(source, language)
        if sup_map:
            findings = [
                f
                for f in findings
                if not is_finding_suppressed(sup_map, f.rule_id, f.span.start_line)
            ]

        all_findings.extend(findings)

    # Sort findings
    all_findings = collect(all_findings)

    # Output results
    total_files = len(files)
    finding_count = len(all_findings)

    if output_format == "json":
        _format_json(all_findings)
    elif output_format == "sarif":
        _format_sarif(all_findings)
    else:
        # Terminal format
        lang_parts = []
        for lang_name in sorted(lang_counts):
            count = lang_counts[lang_name]
            display = lang_name.capitalize()
            lang_parts.append(f"{count} {display}")
        lang_summary = ", ".join(lang_parts)

        console.print(f"Scanned {total_files} files ({lang_summary})")
        console.print(f"   {total_nodes:,} AST nodes analyzed")
        console.print(f"   {finding_count} finding(s)\n")

        if all_findings:
            _format_terminal(all_findings, root, console)
            console.print(f"\n[red]{finding_count} issue(s) found.[/red]\n")
        else:
            console.print("[green]No issues found.[/green]\n")

    # Exit code 1 if findings exist
    if all_findings:
        raise SystemExit(1)
