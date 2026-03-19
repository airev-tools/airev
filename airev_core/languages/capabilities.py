"""Language capability model — centralizes per-language metadata.

This avoids scattering Python/JS/TS assumptions across config, resolver,
file discovery, and ignore handling. New languages register through the
registry instead of modifying scattered conditionals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class LanguageCapabilities:
    """Describes what a language supports for airev analysis."""

    language_id: str
    file_extensions: tuple[str, ...]
    supports_comments: bool
    supports_imports: bool
    supports_string_literals: bool
    manifest_files: tuple[str, ...]
    comment_prefixes: tuple[str, ...] = ()
