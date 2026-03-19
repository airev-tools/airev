"""CLI entry point for airev."""

import click

from interfaces.cli.commands.scan import scan


@click.group()
@click.version_option(version="0.1.0", prog_name="airev")
def cli() -> None:
    """airev — AI code quality scanner."""


cli.add_command(scan)

if __name__ == "__main__":
    cli()
