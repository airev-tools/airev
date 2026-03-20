"""Path safety utilities — prevent symlink loops and path traversal."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def is_path_safe(
    file_path: Path,
    project_root: Path,
) -> bool:
    """Check if a path is safe to access (within project root, no traversal).

    Returns True if the path resolves to within the project root.
    """
    try:
        resolved = file_path.resolve()
        root_resolved = project_root.resolve()
        resolved.relative_to(root_resolved)
        return True
    except (ValueError, OSError):
        return False


def detect_symlink_loop(
    file_path: Path,
    max_depth: int = 40,
) -> bool:
    """Detect symlink loops by checking resolution depth.

    Returns True if a loop is detected.
    """
    try:
        # Python's resolve() already handles symlink loops, raising OSError
        file_path.resolve(strict=True)
        return False
    except OSError:
        return True


def normalize_rel_path(
    file_path: Path,
    project_root: Path,
) -> str | None:
    """Normalize a path relative to project root.

    Returns None if the path escapes the root.
    Uses forward slashes for consistency.
    """
    try:
        resolved = file_path.resolve()
        root_resolved = project_root.resolve()
        rel = resolved.relative_to(root_resolved)
        return str(rel).replace("\\", "/")
    except (ValueError, OSError):
        return None
