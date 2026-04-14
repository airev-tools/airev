"""CLI entry point for airev."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from collections.abc import Sequence

from interfaces.cli.commands.scan import scan

EPILOG = """\b
Examples:
  airev scan .                          Scan current directory
  airev scan src/ --lang python         Scan only Python files
  airev scan . --exclude "tests/**"     Exclude a path pattern
  airev scan . --format sarif           Output as SARIF 2.1.0
  airev scan . --rule phantom-import    Run a single rule
  airev rules                           List all available rules
  airev init                            Create a .airev.toml config file

Docs: https://github.com/airev-tools/airev
"""


class NoGlobGroup(click.Group):
    """Click group that disables Windows wildcard expansion.

    Windows' C runtime expands ``*`` and ``**`` in argv before Click sees them,
    which breaks ``--exclude "tests/**"`` style options.
    """

    def main(
        self,
        args: Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        **extra: Any,
    ) -> Any:
        extra.setdefault("windows_expand_args", False)
        return super().main(
            args,
            prog_name=prog_name,
            complete_var=complete_var,
            standalone_mode=standalone_mode,
            **extra,
        )


@click.group(cls=NoGlobGroup, epilog=EPILOG)
@click.version_option(version="0.2.0", prog_name="airev")
def cli() -> None:
    """airev — AI code quality scanner that catches what copilots miss.

    Detects phantom imports, hallucinated APIs, deprecated APIs,
    hardcoded secrets, and other AI-generated code defects.
    """


@click.command()
def rules() -> None:
    """List all available detection rules."""
    from rich.console import Console
    from rich.table import Table

    from airev_core.rules.common.deprecated_api import DeprecatedApiRule
    from airev_core.rules.common.hallucinated_api import HallucinatedApiRule
    from airev_core.rules.common.hardcoded_secrets import HardcodedSecretsRule
    from airev_core.rules.common.phantom_import import PhantomImportRule
    from airev_core.rules.common.reinvented_internal import ReinventedInternalRule

    console = Console()
    table = Table(title="Available Rules", show_header=True, header_style="bold")
    table.add_column("Rule ID", style="cyan")
    table.add_column("Severity", style="yellow")
    table.add_column("Type")
    table.add_column("Description")

    rule_info: list[tuple[str, str, str, str]] = [
        (
            PhantomImportRule().id,
            PhantomImportRule().severity.value,
            "node",
            "Detects imports of packages/modules that don't exist",
        ),
        (
            HallucinatedApiRule().id,
            HallucinatedApiRule().severity.value,
            "node",
            "Detects calls to non-existent methods on real packages",
        ),
        (
            DeprecatedApiRule().id,
            DeprecatedApiRule().severity.value,
            "node",
            "Detects usage of deprecated/outdated APIs",
        ),
        (
            HardcodedSecretsRule().id,
            HardcodedSecretsRule().severity.value,
            "file",
            "Detects API keys, tokens, and passwords in source code",
        ),
        (
            ReinventedInternalRule().id,
            ReinventedInternalRule().severity.value,
            "file",
            "Detects AI-duplicated utility functions that already exist in the project",
        ),
    ]

    for rule_id, severity, rule_type, description in rule_info:
        table.add_row(rule_id, severity, rule_type, description)

    console.print(table)


@click.command()
@click.option("--force", is_flag=True, default=False, help="Overwrite existing .airev.toml")
def init(force: bool) -> None:
    """Create a .airev.toml configuration file in the current directory."""
    from pathlib import Path

    from rich.console import Console

    console = Console()
    config_path = Path.cwd() / ".airev.toml"

    if config_path.exists() and not force:
        console.print(f"[yellow]{config_path} already exists.[/yellow] Use --force to overwrite.")
        return

    config_path.write_text(
        """\
# airev configuration
# Docs: https://github.com/airev-tools/airev

[airev]
exclude = ["vendor/**", "dist/**", "node_modules/**"]

[rules]
# Disable a rule by setting it to "off"
# phantom-import = "off"
# hallucinated-api = "off"
# deprecated-api = "off"
# hardcoded-secrets = "off"
# reinvented-internal = "off"

# [rules.copy-paste-drift]
# similarity_threshold = 0.8
# min_lines = 10

# [languages]
# enabled = ["python", "typescript"]
""",
        encoding="utf-8",
    )
    console.print(f"[green]Created {config_path}[/green]")


cli.add_command(scan)
cli.add_command(rules)
cli.add_command(init)

if __name__ == "__main__":
    cli()
