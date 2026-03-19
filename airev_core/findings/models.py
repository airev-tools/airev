"""Core data models for airev findings and diagnostics."""

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FixSafety(StrEnum):
    SAFE = "safe"
    UNSAFE = "unsafe"


@dataclass(slots=True, frozen=True)
class SourceSpan:
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    start_byte: int
    end_byte: int


@dataclass(slots=True, frozen=True)
class CodeAction:
    description: str
    replacement: str
    span: SourceSpan
    safety: FixSafety


@dataclass(slots=True, frozen=True)
class Finding:
    rule_id: str
    message: str
    severity: Severity
    file_path: str
    span: SourceSpan
    suggestion: str | None = None
    fix: CodeAction | None = None
    confidence: Confidence = Confidence.HIGH
