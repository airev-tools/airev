"""SARIF 2.1.0 output formatter for GitHub code scanning integration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airev_core.findings.models import Finding

_SARIF_VERSION = "2.1.0"
_SARIF_SCHEMA = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json"
)

_SEVERITY_TO_SARIF_LEVEL: dict[str, str] = {
    "error": "error",
    "warning": "warning",
    "info": "note",
}


def format_sarif(findings: list[Finding], tool_version: str = "0.1.0") -> str:
    """Format findings as a SARIF 2.1.0 JSON string.

    Conforms to the SARIF standard for GitHub code scanning integration.
    """
    # Collect unique rules
    rule_ids: dict[str, int] = {}
    rule_descriptors: list[dict[str, object]] = []

    for f in findings:
        if f.rule_id not in rule_ids:
            rule_ids[f.rule_id] = len(rule_descriptors)
            descriptor: dict[str, object] = {
                "id": f.rule_id,
                "shortDescription": {"text": f.rule_id},
            }
            rule_descriptors.append(descriptor)

    # Build results
    results: list[dict[str, object]] = []
    for f in findings:
        result: dict[str, object] = {
            "ruleId": f.rule_id,
            "ruleIndex": rule_ids[f.rule_id],
            "level": _SEVERITY_TO_SARIF_LEVEL.get(f.severity.value, "warning"),
            "message": {"text": f.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": f.file_path.replace("\\", "/"),
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {
                            "startLine": f.span.start_line,
                            "startColumn": f.span.start_col,
                            "endLine": f.span.end_line,
                            "endColumn": f.span.end_col,
                        },
                    }
                }
            ],
        }

        # Add confidence as a property
        properties: dict[str, str] = {"confidence": f.confidence.value}
        if f.suggestion:
            properties["suggestion"] = f.suggestion
        result["properties"] = properties

        results.append(result)

    sarif: dict[str, object] = {
        "$schema": _SARIF_SCHEMA,
        "version": _SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "airev",
                        "version": tool_version,
                        "informationUri": "https://github.com/airev-tools/airev",
                        "rules": rule_descriptors,
                    }
                },
                "results": results,
            }
        ],
    }

    return json.dumps(sarif, indent=2, ensure_ascii=False)
