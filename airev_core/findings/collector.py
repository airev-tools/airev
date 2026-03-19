"""Finding collector with deduplication and severity-ordered sorting."""

from __future__ import annotations

from airev_core.findings.models import Finding, Severity

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.ERROR: 0,
    Severity.WARNING: 1,
    Severity.INFO: 2,
}


def _dedup_key(f: Finding) -> tuple[str, str, int, int, str]:
    """Generate a deduplication key for a finding."""
    return (f.rule_id, f.file_path, f.span.start_line, f.span.start_col, f.message)


def deduplicate(findings: list[Finding]) -> list[Finding]:
    """Remove duplicate findings (same rule, location, and message)."""
    seen: set[tuple[str, str, int, int, str]] = set()
    result: list[Finding] = []
    for f in findings:
        key = _dedup_key(f)
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Sort findings by severity (error first), then file path, then line."""
    return sorted(
        findings,
        key=lambda f: (
            _SEVERITY_ORDER.get(f.severity, 9),
            f.file_path,
            f.span.start_line,
            f.span.start_col,
        ),
    )


def collect(findings: list[Finding]) -> list[Finding]:
    """Deduplicate and sort findings in one step."""
    return sort_findings(deduplicate(findings))
