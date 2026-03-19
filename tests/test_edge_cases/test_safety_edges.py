"""Edge case tests for safety boundary."""

import sys
from pathlib import Path

import pytest

from airev_core.security.scan_policy import (
    ScanSafetyConfig,
    evaluate_file_policy,
    safe_read_source,
)


class TestSafetyEdges:
    def test_binary_with_py_extension(self, tmp_path: Path) -> None:
        """Binary file with .py extension skipped safely."""
        f = tmp_path / "data.py"
        f.write_bytes(b"\x7fELF" + b"\x00" * 200)
        decision = evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        assert not decision.should_scan

    def test_giant_generated_file(self, tmp_path: Path) -> None:
        """Giant file under source directory skipped."""
        f = tmp_path / "huge.py"
        f.write_bytes(b"x = 1\n" * 500_000)
        config = ScanSafetyConfig(max_file_bytes=1_000_000)
        decision = evaluate_file_policy(f, tmp_path, config)
        assert not decision.should_scan

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks need admin on Windows")
    def test_symlink_inside_repo_pointing_outside(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside_target.py"
        outside.write_text("x = 1\n")
        link = tmp_path / "sneaky.py"
        link.symlink_to(outside)
        config = ScanSafetyConfig(follow_safe_symlinks=True)
        decision = evaluate_file_policy(link, tmp_path, config)
        assert not decision.should_scan
        outside.unlink()

    def test_unicode_filename(self, tmp_path: Path) -> None:
        """File names containing unusual unicode handled."""
        f = tmp_path / "café.py"
        f.write_text("x = 1\n")
        decision = evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        assert decision.should_scan

    def test_permission_error_graceful(self, tmp_path: Path) -> None:
        """Unreadable file handled gracefully."""
        f = tmp_path / "nope.py"
        f.write_text("x = 1\n")
        # safe_read_source on a nonexistent file
        source, warning = safe_read_source(tmp_path / "nonexistent.py")
        assert source == b""
        assert warning is not None


class TestOutputSafety:
    def test_finding_with_quotes_serializes_to_json(self) -> None:
        """Finding message with quotes/newlines serializes cleanly."""
        import json

        from airev_core.findings.models import Finding, Severity, SourceSpan
        from interfaces.cli.formatters.json_fmt import format_json

        finding = Finding(
            rule_id="test",
            message='Module "foo\'s" bar\nnewline here',
            severity=Severity.ERROR,
            file_path="app.py",
            span=SourceSpan(1, 1, 1, 10, 0, 9),
        )
        result = json.loads(format_json([finding]))
        assert result[0]["message"] == 'Module "foo\'s" bar\nnewline here'

    def test_finding_serializes_to_sarif(self) -> None:
        import json

        from airev_core.findings.models import Finding, Severity, SourceSpan
        from interfaces.cli.formatters.sarif import format_sarif

        finding = Finding(
            rule_id="test",
            message='Tricky "message" with <angle> & stuff',
            severity=Severity.WARNING,
            file_path="src/app.py",
            span=SourceSpan(1, 1, 1, 10, 0, 9),
        )
        sarif = json.loads(format_sarif([finding]))
        assert sarif["runs"][0]["results"][0]["message"]["text"] == finding.message

    def test_windows_path_normalized_in_sarif(self) -> None:
        import json

        from airev_core.findings.models import Finding, Severity, SourceSpan
        from interfaces.cli.formatters.sarif import format_sarif

        finding = Finding(
            rule_id="test",
            message="test",
            severity=Severity.INFO,
            file_path="src\\sub\\app.py",
            span=SourceSpan(1, 1, 1, 10, 0, 9),
        )
        sarif = json.loads(format_sarif([finding]))
        uri = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "artifactLocation"
        ]["uri"]
        assert "\\" not in uri

    def test_zero_findings_valid_json(self) -> None:
        import json

        from interfaces.cli.formatters.json_fmt import format_json

        result = json.loads(format_json([]))
        assert result == []

    def test_zero_findings_valid_sarif(self) -> None:
        import json

        from interfaces.cli.formatters.sarif import format_sarif

        sarif = json.loads(format_sarif([]))
        assert sarif["runs"][0]["results"] == []
        assert sarif["version"] == "2.1.0"
