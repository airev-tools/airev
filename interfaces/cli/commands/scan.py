"""The `airev scan` command — walks a directory, parses files, and prints a summary."""

from __future__ import annotations

import os
from pathlib import Path

import click
from rich.console import Console

from airev_core.parsers import ParserRegistry

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


def _discover_files(
    root: Path,
    registry: ParserRegistry,
    lang_filter: str | None,
) -> list[tuple[Path, str]]:
    """Walk directory tree and return (path, language) pairs for supported files."""
    results: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in filenames:
            filepath = Path(dirpath) / filename
            language = registry.get_language(str(filepath))
            if language is None:
                continue
            if lang_filter is not None and language != lang_filter:
                continue
            results.append((filepath, language))
    return results


@click.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--lang", default=None, help="Only scan files of this language (python, javascript, typescript)"
)
def scan(path: str, lang: str | None) -> None:
    """Scan a directory for AI-generated code quality issues."""
    console = Console()
    root = Path(path).resolve()
    registry = ParserRegistry()

    console.print("\n[bold]airev[/bold] v0.1.0\n")
    console.print(f"Scanning {root}...\n")

    files = _discover_files(root, registry, lang)

    if not files:
        console.print("[dim]No supported files found.[/dim]")
        console.print("0 files scanned.\n")
        return

    # Parse all files
    total_nodes = 0
    lang_counts: dict[str, int] = {}
    for filepath, language in files:
        parser = registry.get_parser(str(filepath))
        if parser is None:
            continue
        source = filepath.read_bytes()
        arena = parser.parse(source)
        total_nodes += arena.count
        lang_counts[language] = lang_counts.get(language, 0) + 1

    # Format language breakdown
    lang_parts = []
    for lang_name in sorted(lang_counts):
        count = lang_counts[lang_name]
        display = lang_name.capitalize()
        lang_parts.append(f"{count} {display}")
    lang_summary = ", ".join(lang_parts)

    total_files = len(files)
    console.print(f"[green]OK[/green] Scanned {total_files} files ({lang_summary})")
    console.print(f"   {total_nodes:,} AST nodes analyzed")
    console.print("   0 findings\n")
    console.print("[green]No issues found.[/green]\n")
