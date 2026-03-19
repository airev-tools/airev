"""Reinvented-internal detection — flags functions duplicated from elsewhere in the project."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from airev_core.findings.models import Confidence, Finding, Severity, SourceSpan

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.semantics.context import LintContext

# Directories that suggest utility/shared code
_UTILITY_DIRS: frozenset[str] = frozenset(
    {"utils", "helpers", "lib", "common", "shared", "util", "helper"}
)

# Common function names that are intentionally overridden/duplicated
_EXCLUDED_NAMES: frozenset[str] = frozenset(
    {
        "__init__",
        "__str__",
        "__repr__",
        "__eq__",
        "__hash__",
        "__len__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__iter__",
        "__next__",
        "__enter__",
        "__exit__",
        "setup",
        "teardown",
        "run",
        "execute",
        "process",
        "handle",
        "main",
    }
)

_TEST_FILE_RE: re.Pattern[str] = re.compile(
    r"(?:test_.*\.py|.*_test\.py|.*\.test\.[jt]s|.*\.spec\.[jt]s|conftest\.py)"
)


def _is_test_file(path: str) -> bool:
    """Check if a file path is a test file."""
    name = PurePosixPath(path).name
    return bool(_TEST_FILE_RE.match(name))


def _get_directory(path: str) -> str:
    """Get the parent directory of a file path."""
    return str(PurePosixPath(path).parent)


def _in_utility_dir(path: str) -> bool:
    """Check if a file is under a utility directory."""
    parts = PurePosixPath(path).parts
    return any(p.lower() in _UTILITY_DIRS for p in parts)


class ReinventedInternalRule:
    """Detects when AI generates a function that already exists elsewhere in the project.

    FileRule: scans all function definitions against a project-wide symbol index.
    """

    @property
    def id(self) -> str:
        return "reinvented-internal"

    @property
    def severity(self) -> Severity:
        return Severity.WARNING

    @property
    def languages(self) -> frozenset[str] | None:
        return None

    def evaluate(self, arena: UastArena, ctx: LintContext) -> list[Finding]:
        """Check function definitions against project symbol index."""
        if ctx.project_symbols is None:
            return []

        if _is_test_file(ctx.file_path):
            return []

        current_dir = _get_directory(ctx.file_path)
        findings: list[Finding] = []

        for defn in ctx.semantic.definitions:
            if defn.kind != "function":
                continue

            if defn.name in _EXCLUDED_NAMES:
                continue

            locations = ctx.project_symbols.get(defn.name)
            if locations is None:
                continue

            for other_path, _other_defn in locations:
                # Skip same file
                if other_path == ctx.file_path:
                    continue

                # Skip same directory (intentional module organization)
                if _get_directory(other_path) == current_dir:
                    continue

                # Skip test files as other location
                if _is_test_file(other_path):
                    continue

                # Only flag if the other location is in a utility dir
                # or both files define non-trivial functions
                if not _in_utility_dir(other_path):
                    continue

                findings.append(
                    Finding(
                        rule_id=self.id,
                        message=(
                            f"Function '{defn.name}' already exists in "
                            f"'{other_path}'. Consider reusing the existing implementation."
                        ),
                        severity=self.severity,
                        file_path=ctx.file_path,
                        span=SourceSpan(
                            start_line=int(arena.start_lines[defn.arena_idx]),
                            start_col=int(arena.start_cols[defn.arena_idx]),
                            end_line=int(arena.start_lines[defn.arena_idx]),
                            end_col=int(arena.start_cols[defn.arena_idx]) + len(defn.name),
                            start_byte=int(arena.start_bytes[defn.arena_idx]),
                            end_byte=int(arena.end_bytes[defn.arena_idx]),
                        ),
                        suggestion=f"Import '{defn.name}' from '{other_path}' instead.",
                        confidence=Confidence.MEDIUM,
                    )
                )
                break  # One finding per function is enough

        return findings
