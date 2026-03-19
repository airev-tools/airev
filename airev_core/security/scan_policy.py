"""Scan policy — decides whether a file should be scanned.

All decisions happen BEFORE parsing. This is the safety boundary between
untrusted file system content and the analysis engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(slots=True, frozen=True)
class ScanSafetyConfig:
    """Safety limits for scanning. All values are configurable."""

    max_file_bytes: int = 1_048_576  # 1 MB
    max_line_length_for_parse: int = 20_000
    follow_safe_symlinks: bool = False
    skip_minified: bool = True
    skip_binary: bool = True
    max_total_bytes: int = 200_000_000  # 200 MB
    max_files: int = 50_000


@dataclass(slots=True, frozen=True)
class ScanPolicyDecision:
    """Result of evaluating a file against the scan policy."""

    should_scan: bool
    reason: str | None = None


# Common generated/minified patterns
_MINIFIED_SUFFIXES = frozenset({".min.js", ".min.css", ".min.mjs"})

_GENERATED_PATTERNS = frozenset(
    {
        ".generated.",
        ".auto.",
        "_generated.",
        "_auto.",
        "pb.go",
        "_pb2.py",
        ".pb.",
    }
)

# Binary file signatures (first few bytes)
_BINARY_SIGNATURES = (
    b"\x89PNG",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF8",  # GIF
    b"PK\x03\x04",  # ZIP/DOCX/XLSX
    b"\x7fELF",  # ELF binary
    b"MZ",  # Windows PE
    b"\x00asm",  # WASM
    b"\xca\xfe\xba\xbe",  # Mach-O/Java class
)

# NUL byte threshold — if more than this fraction are NUL, treat as binary
_NUL_THRESHOLD = 0.05


def evaluate_file_policy(
    file_path: Path,
    project_root: Path,
    config: ScanSafetyConfig,
) -> ScanPolicyDecision:
    """Evaluate whether a file should be scanned.

    This is the safety boundary. Runs before any parsing.
    """
    # 1. Path safety — must be within project root
    try:
        resolved = file_path.resolve()
    except (OSError, ValueError):
        return ScanPolicyDecision(should_scan=False, reason="path resolution failed")

    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return ScanPolicyDecision(should_scan=False, reason="path escapes project root")

    # 2. Symlink handling
    if file_path.is_symlink():
        if not config.follow_safe_symlinks:
            return ScanPolicyDecision(
                should_scan=False, reason="symlink skipped (follow_safe_symlinks=false)"
            )
        # Even with follow enabled, target must be inside project root
        try:
            target = file_path.resolve(strict=True)
            target.relative_to(project_root.resolve())
        except (ValueError, OSError):
            return ScanPolicyDecision(
                should_scan=False, reason="symlink target escapes project root"
            )

    # 3. File size
    try:
        stat = file_path.stat()
    except OSError:
        return ScanPolicyDecision(should_scan=False, reason="cannot stat file")

    if stat.st_size > config.max_file_bytes:
        return ScanPolicyDecision(
            should_scan=False,
            reason=f"file too large ({stat.st_size} > {config.max_file_bytes})",
        )

    if stat.st_size == 0:
        return ScanPolicyDecision(should_scan=False, reason="empty file")

    # 4. Minified file detection
    name = file_path.name.lower()
    if config.skip_minified:
        for suffix in _MINIFIED_SUFFIXES:
            if name.endswith(suffix):
                return ScanPolicyDecision(should_scan=False, reason="minified file skipped")

    # 5. Generated file detection
    for pattern in _GENERATED_PATTERNS:
        if pattern in name:
            return ScanPolicyDecision(should_scan=False, reason="generated file skipped")

    # 6. Binary file detection
    if config.skip_binary:
        try:
            with open(file_path, "rb") as f:
                header = f.read(512)
        except OSError:
            return ScanPolicyDecision(should_scan=False, reason="cannot read file")

        # Check magic bytes
        for sig in _BINARY_SIGNATURES:
            if header.startswith(sig):
                return ScanPolicyDecision(should_scan=False, reason="binary file skipped")

        # Check NUL byte ratio
        if header:
            nul_count = header.count(b"\x00")
            if nul_count / len(header) > _NUL_THRESHOLD:
                return ScanPolicyDecision(
                    should_scan=False, reason="binary file skipped (NUL bytes)"
                )

    return ScanPolicyDecision(should_scan=True)


def check_long_lines(
    source: bytes,
    config: ScanSafetyConfig,
) -> bool:
    """Check if any line exceeds the max line length threshold.

    Returns True if the file should be skipped due to extremely long lines.
    """
    return any(len(line) > config.max_line_length_for_parse for line in source.split(b"\n"))


def safe_read_source(file_path: Path) -> tuple[bytes, str | None]:
    """Read source file with decode safety.

    Returns (source_bytes, warning_message).
    Warning is None on clean read, non-None if fallback decoding was used.
    """
    try:
        raw = file_path.read_bytes()
    except OSError as e:
        return b"", f"cannot read file: {e}"

    # Try UTF-8 strict first
    try:
        raw.decode("utf-8")
        return raw, None
    except UnicodeDecodeError:
        # Fall back to tolerant mode — file is readable but has encoding issues
        return raw, "file contains invalid UTF-8, decoded with replacement characters"
