"""JSON output formatter for airev findings."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airev_core.findings.models import Finding


def format_json(findings: list[Finding]) -> str:
    """Format findings as a JSON array string."""
    output = [
        {
            "rule_id": f.rule_id,
            "message": f.message,
            "severity": f.severity.value,
            "confidence": f.confidence.value,
            "file_path": f.file_path,
            "start_line": f.span.start_line,
            "start_col": f.span.start_col,
            "end_line": f.span.end_line,
            "end_col": f.span.end_col,
            "suggestion": f.suggestion,
        }
        for f in findings
    ]
    return json.dumps(output, indent=2, ensure_ascii=False)
