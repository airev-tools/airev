"""Workspace facts data models — immutable, pickle-safe, language-neutral."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class WorkspaceFacts:
    """Immutable summary of workspace structure, built once per scan.

    Contains cheap-to-collect facts about the project layout, manifests,
    and dependency declarations. Used to improve rule accuracy without
    heavy analysis.
    """

    project_root: str
    languages: frozenset[str]
    manifest_paths: tuple[str, ...]
    first_party_prefixes: frozenset[str]
    third_party_dependencies: frozenset[str]
    python_module_roots: tuple[str, ...]
    package_names: frozenset[str]
    ts_path_aliases: tuple[tuple[str, str], ...]
    has_lockfile: bool
