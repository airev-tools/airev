""".airevignore — gitignore-style file exclusion patterns.

Patterns follow the same syntax as .gitignore:
- blank lines and lines starting with # are ignored
- standard glob patterns work
- patterns ending with / only match directories
- patterns starting with / are anchored to the project root
- patterns starting with ! negate a previous exclusion
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(slots=True, frozen=True)
class IgnorePattern:
    """A single parsed ignore pattern."""

    pattern: str
    regex: re.Pattern[str]
    negated: bool
    dir_only: bool


def parse_ignorefile(content: str) -> tuple[IgnorePattern, ...]:
    """Parse .airevignore content into a tuple of patterns."""
    patterns: list[IgnorePattern] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        negated = line.startswith("!")
        if negated:
            line = line[1:]

        dir_only = line.endswith("/")
        if dir_only:
            line = line.rstrip("/")

        # Convert gitignore glob to regex
        regex_str = _glob_to_regex(line)
        regex = re.compile(regex_str)
        patterns.append(
            IgnorePattern(
                pattern=raw_line.strip(),
                regex=regex,
                negated=negated,
                dir_only=dir_only,
            )
        )

    return tuple(patterns)


def _glob_to_regex(pattern: str) -> str:
    """Convert a gitignore-style glob to a regex pattern.

    Anchored patterns (starting with /) match from root.
    Unanchored patterns match any path component.
    ** matches any number of directories.
    """
    anchored = pattern.startswith("/")
    if anchored:
        pattern = pattern[1:]

    # Split on ** to handle directory wildcards
    parts = pattern.split("**")
    regex_parts: list[str] = []

    for part in parts:
        # Convert each part using fnmatch translation
        translated = fnmatch.translate(part)
        # fnmatch.translate adds \Z at end and (?s:...) wrapper — strip them
        translated = translated.removeprefix("(?s:")
        translated = translated.removesuffix(")\\Z")
        regex_parts.append(translated)

    # Join parts with "any directories" pattern
    joined = ".*".join(regex_parts)

    if anchored:
        return f"^{joined}$"
    # Unanchored: match anywhere in the path
    return f"(?:^|/){joined}$"


def load_ignorefile(project_root: str) -> tuple[IgnorePattern, ...]:
    """Load .airevignore from the project root, returning empty tuple if not found."""
    ignore_path = PurePosixPath(project_root) / ".airevignore"
    try:
        # Use raw Path for actual file I/O
        from pathlib import Path

        content = Path(str(ignore_path)).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ()
    return parse_ignorefile(content)


def is_ignored(
    rel_path: str,
    patterns: tuple[IgnorePattern, ...],
    is_dir: bool = False,
) -> bool:
    """Check if a relative path should be ignored based on patterns.

    Args:
        rel_path: Path relative to project root, using forward slashes.
        patterns: Parsed ignore patterns from parse_ignorefile().
        is_dir: True if the path is a directory.

    Returns:
        True if the path should be excluded.
    """
    # Normalize to forward slashes
    normalized = rel_path.replace("\\", "/").lstrip("/")

    ignored = False
    for pat in patterns:
        if pat.dir_only and not is_dir:
            continue

        if pat.regex.search(normalized):
            ignored = not pat.negated

    return ignored
