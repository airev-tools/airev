"""Tests for the finding collector (deduplication + sorting)."""

from __future__ import annotations

from airev_core.findings.collector import collect, deduplicate, sort_findings
from airev_core.findings.models import Confidence, Finding, Severity, SourceSpan


def _make_finding(
    rule_id: str = "test-rule",
    message: str = "test message",
    severity: Severity = Severity.WARNING,
    file_path: str = "test.py",
    start_line: int = 1,
    start_col: int = 0,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        message=message,
        severity=severity,
        file_path=file_path,
        span=SourceSpan(
            start_line=start_line,
            start_col=start_col,
            end_line=start_line,
            end_col=start_col + 10,
            start_byte=0,
            end_byte=10,
        ),
        confidence=Confidence.HIGH,
    )


class TestDeduplicate:
    def test_removes_exact_duplicates(self) -> None:
        f = _make_finding()
        result = deduplicate([f, f, f])
        assert len(result) == 1

    def test_keeps_different_findings(self) -> None:
        f1 = _make_finding(rule_id="rule-a")
        f2 = _make_finding(rule_id="rule-b")
        result = deduplicate([f1, f2])
        assert len(result) == 2

    def test_preserves_order(self) -> None:
        f1 = _make_finding(rule_id="rule-a")
        f2 = _make_finding(rule_id="rule-b")
        result = deduplicate([f1, f2, f1])
        assert result[0].rule_id == "rule-a"
        assert result[1].rule_id == "rule-b"

    def test_empty_list(self) -> None:
        assert deduplicate([]) == []


class TestSortFindings:
    def test_sorts_by_severity(self) -> None:
        f_info = _make_finding(severity=Severity.INFO)
        f_error = _make_finding(severity=Severity.ERROR)
        f_warn = _make_finding(severity=Severity.WARNING)
        result = sort_findings([f_info, f_error, f_warn])
        assert result[0].severity == Severity.ERROR
        assert result[1].severity == Severity.WARNING
        assert result[2].severity == Severity.INFO

    def test_sorts_by_file_within_severity(self) -> None:
        f_b = _make_finding(file_path="b.py")
        f_a = _make_finding(file_path="a.py")
        result = sort_findings([f_b, f_a])
        assert result[0].file_path == "a.py"
        assert result[1].file_path == "b.py"

    def test_sorts_by_line_within_file(self) -> None:
        f2 = _make_finding(start_line=10)
        f1 = _make_finding(start_line=1)
        result = sort_findings([f2, f1])
        assert result[0].span.start_line == 1
        assert result[1].span.start_line == 10


class TestCollect:
    def test_deduplicates_and_sorts(self) -> None:
        f_dup = _make_finding(severity=Severity.INFO)
        f_error = _make_finding(severity=Severity.ERROR, message="error msg")
        result = collect([f_dup, f_error, f_dup])
        assert len(result) == 2
        assert result[0].severity == Severity.ERROR
        assert result[1].severity == Severity.INFO
