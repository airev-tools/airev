"""Tests for JSON and SARIF output formatters."""

import json

from airev_core.findings.models import Finding, Severity, SourceSpan
from interfaces.cli.formatters.json_fmt import format_json
from interfaces.cli.formatters.sarif import format_sarif


def _make_finding(
    rule_id: str = "phantom-import",
    message: str = "Module 'foo' not found",
    severity: Severity = Severity.ERROR,
    file_path: str = "src/app.py",
    line: int = 1,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        message=message,
        severity=severity,
        file_path=file_path,
        span=SourceSpan(
            start_line=line,
            start_col=1,
            end_line=line,
            end_col=20,
            start_byte=0,
            end_byte=19,
        ),
    )


class TestJsonFormat:
    def test_empty(self) -> None:
        result = json.loads(format_json([]))
        assert result == []

    def test_single_finding(self) -> None:
        findings = [_make_finding()]
        result = json.loads(format_json(findings))
        assert len(result) == 1
        assert result[0]["rule_id"] == "phantom-import"
        assert result[0]["severity"] == "error"
        assert result[0]["start_line"] == 1

    def test_multiple_findings(self) -> None:
        findings = [
            _make_finding(rule_id="phantom-import"),
            _make_finding(rule_id="hardcoded-secrets", severity=Severity.WARNING),
        ]
        result = json.loads(format_json(findings))
        assert len(result) == 2

    def test_special_characters(self) -> None:
        finding = _make_finding(message='Module "foo\'s" bar not found\nnewline')
        result = json.loads(format_json([finding]))
        assert result[0]["message"] == 'Module "foo\'s" bar not found\nnewline'


class TestSarifFormat:
    def test_valid_sarif_structure(self) -> None:
        findings = [_make_finding()]
        sarif = json.loads(format_sarif(findings))
        assert sarif["version"] == "2.1.0"
        assert "$schema" in sarif
        assert len(sarif["runs"]) == 1

    def test_tool_info(self) -> None:
        sarif = json.loads(format_sarif([_make_finding()]))
        tool = sarif["runs"][0]["tool"]["driver"]
        assert tool["name"] == "airev"
        assert "version" in tool
        assert "rules" in tool

    def test_results(self) -> None:
        findings = [_make_finding()]
        sarif = json.loads(format_sarif(findings))
        results = sarif["runs"][0]["results"]
        assert len(results) == 1
        assert results[0]["ruleId"] == "phantom-import"
        assert results[0]["level"] == "error"
        assert results[0]["message"]["text"] == "Module 'foo' not found"

    def test_location(self) -> None:
        sarif = json.loads(format_sarif([_make_finding()]))
        loc = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"] == "src/app.py"
        region = loc["region"]
        assert region["startLine"] == 1
        assert region["startColumn"] == 1

    def test_multiple_rules_indexed(self) -> None:
        findings = [
            _make_finding(rule_id="phantom-import"),
            _make_finding(rule_id="hardcoded-secrets"),
            _make_finding(rule_id="phantom-import"),
        ]
        sarif = json.loads(format_sarif(findings))
        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 2  # Deduplicated

    def test_empty_findings(self) -> None:
        sarif = json.loads(format_sarif([]))
        assert sarif["runs"][0]["results"] == []

    def test_confidence_in_properties(self) -> None:
        finding = _make_finding()
        sarif = json.loads(format_sarif([finding]))
        props = sarif["runs"][0]["results"][0]["properties"]
        assert props["confidence"] == "high"

    def test_suggestion_in_properties(self) -> None:
        finding = Finding(
            rule_id="deprecated-api",
            message="os.popen is deprecated",
            severity=Severity.WARNING,
            file_path="app.py",
            span=SourceSpan(1, 1, 1, 10, 0, 9),
            suggestion="Use subprocess.run() instead",
        )
        sarif = json.loads(format_sarif([finding]))
        props = sarif["runs"][0]["results"][0]["properties"]
        assert props["suggestion"] == "Use subprocess.run() instead"

    def test_severity_mapping(self) -> None:
        for sev, expected_level in [
            (Severity.ERROR, "error"),
            (Severity.WARNING, "warning"),
            (Severity.INFO, "note"),
        ]:
            finding = _make_finding(severity=sev)
            sarif = json.loads(format_sarif([finding]))
            assert sarif["runs"][0]["results"][0]["level"] == expected_level

    def test_windows_path_normalized(self) -> None:
        finding = _make_finding(file_path="src\\app.py")
        sarif = json.loads(format_sarif([finding]))
        uri = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "artifactLocation"
        ]["uri"]
        assert "\\" not in uri
