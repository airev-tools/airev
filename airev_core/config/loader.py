"""Configuration loader — reads .airev.toml or [tool.airev] from pyproject.toml.

Loads config once per scan. Does NOT load any config from inside the target repo
if the target repo is different from the working directory (safety boundary).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from airev_core.config.models import AirevConfig, RuleConfig
from airev_core.findings.models import Severity

_VALID_SEVERITIES = frozenset({"error", "warning", "info", "off"})


def load_config(project_root: str) -> AirevConfig:
    """Load configuration from .airev.toml or pyproject.toml in project_root.

    .airev.toml takes precedence over pyproject.toml.
    Returns default config if neither file exists.
    """
    root = Path(project_root)

    # Try .airev.toml first
    airev_toml = root / ".airev.toml"
    if airev_toml.is_file():
        try:
            raw = tomllib.loads(airev_toml.read_text(encoding="utf-8"))
            return _parse_config(raw)
        except (tomllib.TOMLDecodeError, OSError):
            return AirevConfig()

    # Fall back to pyproject.toml [tool.airev]
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            raw = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            airev_section = raw.get("tool", {}).get("airev", {})
            if airev_section:
                return _parse_config(airev_section)
        except (tomllib.TOMLDecodeError, OSError):
            return AirevConfig()

    return AirevConfig()


def _parse_config(raw: dict[str, object]) -> AirevConfig:
    """Parse a raw TOML dict into an AirevConfig."""
    # Parse exclude
    exclude_raw = raw.get("exclude", [])
    exclude: tuple[str, ...] = ()
    if isinstance(exclude_raw, list):
        exclude = tuple(str(e) for e in exclude_raw)

    # Parse languages
    languages: frozenset[str] | None = None
    languages_section = raw.get("languages")
    if isinstance(languages_section, dict):
        enabled = languages_section.get("enabled")
        if isinstance(enabled, list):
            languages = frozenset(str(lang) for lang in enabled)

    # Parse rules
    rules: dict[str, RuleConfig] = {}
    rules_section = raw.get("rules")
    if isinstance(rules_section, dict):
        for key, value in rules_section.items():
            if isinstance(value, str):
                # Simple form: rule_id = "off" / "error" / "warning" / "info"
                if value == "off":
                    rules[key] = RuleConfig(enabled=False)
                elif value in _VALID_SEVERITIES:
                    rules[key] = RuleConfig(severity=Severity(value))
            elif isinstance(value, dict):
                # Detailed form: [rules.rule-id]
                enabled = value.get("enabled", True)
                sev_str = value.get("severity")
                severity: Severity | None = None
                if isinstance(sev_str, str) and sev_str in _VALID_SEVERITIES:
                    if sev_str == "off":
                        enabled = False
                    else:
                        severity = Severity(sev_str)
                options = {k: v for k, v in value.items() if k not in ("enabled", "severity")}
                rules[key] = RuleConfig(
                    enabled=bool(enabled),
                    severity=severity,
                    options=options,
                )

    return AirevConfig(exclude=exclude, rules=rules, languages=languages)
