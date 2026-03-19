"""Configuration data models for airev."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airev_core.findings.models import Severity


@dataclass(slots=True, frozen=True)
class RuleConfig:
    """Configuration for a single rule."""

    enabled: bool = True
    severity: Severity | None = None
    options: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class AirevConfig:
    """Top-level airev configuration, loaded from .airev.toml or pyproject.toml."""

    exclude: tuple[str, ...] = ()
    rules: dict[str, RuleConfig] = field(default_factory=dict)
    languages: frozenset[str] | None = None
