"""Hardcoded secrets detection — regex patterns, Shannon entropy, false-positive suppression."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from airev_core.findings.models import Confidence, Finding, Severity, SourceSpan
from airev_core.heuristics.patterns import shannon_entropy

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena
    from airev_core.semantics.context import LintContext

# ---------------------------------------------------------------------------
# Test file patterns (these files are excluded from scanning)
# ---------------------------------------------------------------------------
_TEST_FILE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"test_.*\.py$"),
    re.compile(r".*_test\.py$"),
    re.compile(r".*\.test\.[jt]s$"),
    re.compile(r".*\.spec\.[jt]s$"),
)

# ---------------------------------------------------------------------------
# Layer 1: Known secret patterns (regex)
# ---------------------------------------------------------------------------
_KNOWN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key ID detected"),
    (
        re.compile(
            r"(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)"
            r"""\s*[=:]\s*["']?([A-Za-z0-9/+=]{40})["']?"""
        ),
        "AWS Secret Access Key detected",
    ),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}"), "GitHub Token detected"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,255}"), "GitHub Fine-Grained PAT detected"),
    (re.compile(r"xox[baprs]-[0-9]{10,13}-[A-Za-z0-9-]+"), "Slack Token detected"),
    (re.compile(r"(?:sk|pk)_live_[A-Za-z0-9]{20,}"), "Stripe Key detected"),
    (re.compile(r"-----BEGIN\s+[\w\s]*PRIVATE KEY"), "Private Key block detected"),
    (
        re.compile(r"(?:mongodb|postgres|mysql|redis)://[^\s\"':]+:[^\s\"'@]+@"),
        "Database connection string with embedded credentials",
    ),
)

# ---------------------------------------------------------------------------
# Layer 2: Suspicious variable name patterns
# ---------------------------------------------------------------------------
_SUSPICIOUS_VAR_RE: re.Pattern[str] = re.compile(
    r"(?:api[_-]?key|api[_-]?secret|secret[_-]?key|secret|token|password|passwd|pwd"
    r"|credential|auth[_-]?token|access[_-]?key|private[_-]?key)",
    re.IGNORECASE,
)

_PASSWORD_VAR_RE: re.Pattern[str] = re.compile(
    r"^(?:password|passwd|pwd)$",
    re.IGNORECASE,
)

_GENERIC_KEY_VAR_RE: re.Pattern[str] = re.compile(
    r"(?:api[_-]?key|secret[_-]?key|token|api[_-]?secret|access[_-]?key|private[_-]?key"
    r"|auth[_-]?token|secret|credential)",
    re.IGNORECASE,
)

# Matches variable = "string" assignments in Python and JS/TS
_ASSIGNMENT_RE: re.Pattern[str] = re.compile(
    r"""(?:(?:const|let|var|export)\s+)?(\w+)\s*[:=]\s*f?['"](.+?)['"]"""
)

# ---------------------------------------------------------------------------
# Layer 3: False-positive suppression
# ---------------------------------------------------------------------------
_PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "your-api-key",
    "your-key",
    "your-secret",
    "your-token",
    "your_api_key",
    "your_key",
    "your_secret",
    "your_token",
    "changeme",
    "change_me",
    "replace-me",
    "replace_me",
    "insert-your",
    "insert_your",
    "<your-",
    "<api-key>",
    "<token>",
    "<secret>",
)

_PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        "your-api-key-here",
        "your_api_key_here",
        "todo",
        "changeme",
        "change_me",
        "xxx",
        "xxxx",
        "xxxxx",
        "***",
        "****",
        "*****",
        "placeholder",
        "example",
        "test",
        "sample",
        "dummy",
        "mock",
        "fake",
        "insert-your-key-here",
        "insert_your_key",
        "replace-me",
        "replace_me",
    }
)

_DUMMY_VAR_NAMES: frozenset[str] = frozenset(
    {"example", "sample", "placeholder", "dummy", "mock", "fake", "test", "demo", "template"}
)

_ENV_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"os\.environ\b"),
    re.compile(r"os\.getenv\b"),
    re.compile(r"process\.env\."),
)

_COMMENT_PREFIXES: tuple[str, ...] = ("#", "//", "/*", "*")

_KNOWN_HASHES: frozenset[str] = frozenset(
    {
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "d41d8cd98f00b204e9800998ecf8427e",
        "da39a3ee5e6b4b0d3255bfef95601890afd80709",
    }
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _is_test_file(file_path: str) -> bool:
    """Check if the file path matches test file patterns."""
    name = PurePosixPath(file_path).name
    return any(pat.search(name) for pat in _TEST_FILE_PATTERNS)


def _is_comment_line(line: str) -> bool:
    """Check if a line is a comment."""
    stripped = line.strip()
    return any(stripped.startswith(p) for p in _COMMENT_PREFIXES)


def _is_env_reference(line: str) -> bool:
    """Check if the line references an environment variable."""
    return any(pat.search(line) for pat in _ENV_PATTERNS)


def _is_file_path(value: str) -> bool:
    """Check if a value looks like a file path."""
    return value.startswith(("/", "./", "../", "~"))


def _is_placeholder(value: str) -> bool:
    """Check if a value is a known placeholder."""
    lower = value.lower().strip()
    if lower in _PLACEHOLDER_VALUES:
        return True
    if any(marker in lower for marker in _PLACEHOLDER_MARKERS):
        return True
    # Repeated characters
    return bool(len(set(lower)) <= 2 and len(lower) > 0)


def _is_known_hash(value: str) -> bool:
    """Check if a value is a known hash constant."""
    return value.lower() in _KNOWN_HASHES


def _is_base64_binary(value: str) -> bool:
    """Check if a value looks like base64-encoded binary data (not a credential)."""
    return value.startswith(("iVBOR", "/9j/", "JVBER"))


def _already_flagged(findings: list[Finding], line_num: int) -> bool:
    """Check if a line was already flagged by a previous pattern."""
    return any(f.span.start_line == line_num for f in findings)


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------
class HardcodedSecretsRule:
    """Detects hardcoded secrets, tokens, passwords, and credentials in source code.

    Three-layer detection:
    1. Known regex patterns (AWS keys, GitHub tokens, Stripe keys, etc.)
    2. Shannon entropy on suspicious variable assignments
    3. False-positive suppression (placeholders, env vars, test files)
    """

    @property
    def id(self) -> str:
        return "hardcoded-secrets"

    @property
    def severity(self) -> Severity:
        return Severity.WARNING

    @property
    def languages(self) -> frozenset[str] | None:
        return None  # All languages

    def evaluate(self, arena: UastArena, ctx: LintContext) -> list[Finding]:
        """Scan source for hardcoded secrets."""
        if _is_test_file(ctx.file_path):
            return []

        source_text = ctx.source.decode("utf-8", errors="replace")
        lines = source_text.splitlines()
        findings: list[Finding] = []
        byte_offset = 0

        for line_idx, line in enumerate(lines):
            line_num = line_idx + 1
            line_bytes = len(line.encode("utf-8")) + 1  # +1 for newline

            # Skip comment lines
            if _is_comment_line(line):
                byte_offset += line_bytes
                continue

            # Skip lines referencing environment variables
            if _is_env_reference(line):
                byte_offset += line_bytes
                continue

            # --- Layer 1: Known regex patterns ---
            for pattern, message in _KNOWN_PATTERNS:
                match = pattern.search(line)
                if (
                    match
                    and not _is_placeholder(match.group(0))
                    and not _is_known_hash(match.group(0))
                ):
                    findings.append(
                        _make_finding(
                            rule_id=self.id,
                            message=message,
                            severity=self.severity,
                            file_path=ctx.file_path,
                            line_num=line_num,
                            col=match.start(),
                            end_col=match.end(),
                            byte_offset=byte_offset + match.start(),
                            end_byte=byte_offset + match.end(),
                        )
                    )

            # --- Layer 1 (generic) + Layer 2: Assignment checks ---
            assign_match = _ASSIGNMENT_RE.search(line)
            if assign_match and not _already_flagged(findings, line_num):
                var_name = assign_match.group(1)
                value = assign_match.group(2)

                if var_name.lower() in _DUMMY_VAR_NAMES:
                    byte_offset += line_bytes
                    continue

                # Skip f-strings / template literals with variable references
                if "{" in value and "}" in value:
                    byte_offset += line_bytes
                    continue

                if not value or _is_placeholder(value) or _is_file_path(value):
                    byte_offset += line_bytes
                    continue

                if _is_known_hash(value) or _is_base64_binary(value):
                    byte_offset += line_bytes
                    continue

                finding: Finding | None = None

                # Generic password variable with any string value
                if _PASSWORD_VAR_RE.search(var_name):
                    finding = _make_finding(
                        rule_id=self.id,
                        message=f"Hardcoded password in variable '{var_name}'",
                        severity=self.severity,
                        file_path=ctx.file_path,
                        line_num=line_num,
                        col=assign_match.start(2),
                        end_col=assign_match.end(2),
                        byte_offset=byte_offset + assign_match.start(2),
                        end_byte=byte_offset + assign_match.end(2),
                    )
                # Generic key/token/secret variable with 20+ char value
                elif _GENERIC_KEY_VAR_RE.search(var_name) and len(value) >= 20:
                    finding = _make_finding(
                        rule_id=self.id,
                        message=(
                            f"Potential secret in variable '{var_name}' (length={len(value)})"
                        ),
                        severity=self.severity,
                        file_path=ctx.file_path,
                        line_num=line_num,
                        col=assign_match.start(2),
                        end_col=assign_match.end(2),
                        byte_offset=byte_offset + assign_match.start(2),
                        end_byte=byte_offset + assign_match.end(2),
                        confidence=Confidence.MEDIUM,
                    )
                # Layer 2: Entropy check on any suspicious variable name
                elif (
                    _SUSPICIOUS_VAR_RE.search(var_name)
                    and len(value) > 20
                    and shannon_entropy(value) > 4.5
                ):
                    finding = _make_finding(
                        rule_id=self.id,
                        message=(
                            f"High-entropy string assigned to suspicious variable '{var_name}'"
                        ),
                        severity=self.severity,
                        file_path=ctx.file_path,
                        line_num=line_num,
                        col=assign_match.start(2),
                        end_col=assign_match.end(2),
                        byte_offset=byte_offset + assign_match.start(2),
                        end_byte=byte_offset + assign_match.end(2),
                        confidence=Confidence.MEDIUM,
                    )

                if finding is not None:
                    findings.append(finding)

            byte_offset += line_bytes

        return findings


def _make_finding(
    *,
    rule_id: str,
    message: str,
    severity: Severity,
    file_path: str,
    line_num: int,
    col: int,
    end_col: int,
    byte_offset: int,
    end_byte: int,
    confidence: Confidence = Confidence.HIGH,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        message=message,
        severity=severity,
        file_path=file_path,
        span=SourceSpan(
            start_line=line_num,
            start_col=col,
            end_line=line_num,
            end_col=end_col,
            start_byte=byte_offset,
            end_byte=end_byte,
        ),
        confidence=confidence,
    )
