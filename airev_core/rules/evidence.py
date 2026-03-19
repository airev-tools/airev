"""Evidence-based confidence calibration for findings.

Rules remain pure — this module provides helper functions that rules
can optionally call to adjust confidence based on workspace context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airev_core.findings.models import Confidence
    from airev_core.semantics.context import LintContext


@dataclass(slots=True, frozen=True)
class EvidenceFlags:
    """Evidence signals that affect finding confidence."""

    dependency_manifest_present: bool = False
    dependencies_installed: bool = False
    import_matches_first_party_prefix: bool = False
    import_matches_declared_dependency: bool = False
    import_matches_tsconfig_alias: bool = False
    file_is_generated: bool = False


def gather_evidence(
    module_name: str,
    ctx: LintContext,
) -> EvidenceFlags:
    """Gather evidence about a module import from workspace context.

    This is cheap — just dict lookups against pre-built workspace facts.
    """
    facts = ctx.workspace_facts
    if facts is None:
        return EvidenceFlags()

    top_level = module_name.split(".")[0]

    # Check first-party prefix
    matches_first_party = top_level in facts.first_party_prefixes

    # Check declared dependency
    matches_declared = module_name in facts.third_party_dependencies or (
        top_level in facts.third_party_dependencies
    )

    # Check TS path alias
    matches_alias = False
    for alias, _target in facts.ts_path_aliases:
        # Handle wildcard aliases like @utils/*
        alias_prefix = alias.rstrip("*").rstrip("/")
        if module_name.startswith(alias_prefix):
            matches_alias = True
            break

    # Check if dependencies are installed
    deps_installed = not ctx.resolver.is_degraded

    return EvidenceFlags(
        dependency_manifest_present=bool(facts.manifest_paths),
        dependencies_installed=deps_installed,
        import_matches_first_party_prefix=matches_first_party,
        import_matches_declared_dependency=matches_declared,
        import_matches_tsconfig_alias=matches_alias,
    )


def calibrate_confidence(
    evidence: EvidenceFlags,
    base_confidence: Confidence,
) -> Confidence:
    """Adjust confidence based on evidence signals.

    Rules:
    - If import matches first-party prefix or TS alias, suppress (return None equivalent)
    - If dependencies not installed, downgrade to MEDIUM or LOW
    - If declared dependency but not installed, stay MEDIUM
    - If generated file, downgrade to LOW
    """
    from airev_core.findings.models import Confidence

    # Generated files get low confidence
    if evidence.file_is_generated:
        return Confidence.LOW

    # Import matches first-party prefix — shouldn't be flagged as phantom
    if evidence.import_matches_first_party_prefix:
        return Confidence.LOW

    # Import matches TS path alias — should not be phantom
    if evidence.import_matches_tsconfig_alias:
        return Confidence.LOW

    # Declared dependency but not installed — medium confidence
    if evidence.import_matches_declared_dependency and not evidence.dependencies_installed:
        return Confidence.MEDIUM

    # No manifest at all — low confidence for phantom/hallucinated
    if not evidence.dependency_manifest_present and not evidence.dependencies_installed:
        return Confidence.LOW

    return base_confidence
