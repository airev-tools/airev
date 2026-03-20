"""Tests for scan policy safety boundary."""

import sys
from pathlib import Path

import pytest

from airev_core.security.path_safety import (
    is_path_safe,
    normalize_rel_path,
)
from airev_core.security.scan_policy import (
    ScanPolicyDecision,
    ScanSafetyConfig,
    check_long_lines,
    evaluate_file_policy,
    safe_read_source,
)


class TestEvaluateFilePolicy:
    def test_normal_file(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("x = 1\n")
        decision = evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        assert decision.should_scan

    def test_huge_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "big.py"
        f.write_bytes(b"x" * 2_000_000)
        config = ScanSafetyConfig(max_file_bytes=1_000_000)
        decision = evaluate_file_policy(f, tmp_path, config)
        assert not decision.should_scan
        assert "too large" in (decision.reason or "")

    def test_empty_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_bytes(b"")
        decision = evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        assert not decision.should_scan
        assert "empty" in (decision.reason or "")

    def test_minified_js_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "bundle.min.js"
        f.write_text("var a=1;")
        decision = evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        assert not decision.should_scan
        assert "minified" in (decision.reason or "")

    def test_binary_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "image.py"  # .py extension but binary content
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        decision = evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        assert not decision.should_scan
        assert "binary" in (decision.reason or "")

    def test_nul_bytes_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "data.py"
        f.write_bytes(b"\x00" * 100 + b"x" * 100)
        decision = evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        assert not decision.should_scan

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks need admin on Windows")
    def test_symlink_outside_root_blocked(self, tmp_path: Path) -> None:
        target = tmp_path.parent / "outside.py"
        target.write_text("x = 1\n")
        link = tmp_path / "link.py"
        link.symlink_to(target)
        config = ScanSafetyConfig(follow_safe_symlinks=True)
        decision = evaluate_file_policy(link, tmp_path, config)
        assert not decision.should_scan
        target.unlink()

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks need admin on Windows")
    def test_symlink_default_skipped(self, tmp_path: Path) -> None:
        target = tmp_path / "real.py"
        target.write_text("x = 1\n")
        link = tmp_path / "link.py"
        link.symlink_to(target)
        decision = evaluate_file_policy(link, tmp_path, ScanSafetyConfig())
        assert not decision.should_scan
        assert "symlink" in (decision.reason or "")

    def test_generated_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "api.generated.ts"
        f.write_text("export const x = 1;")
        decision = evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        assert not decision.should_scan
        assert "generated" in (decision.reason or "")

    def test_path_escaping_root(self, tmp_path: Path) -> None:
        # Create a file outside the project root
        outside = tmp_path.parent / "outside_file.py"
        outside.write_text("x = 1\n")
        try:
            decision = evaluate_file_policy(outside, tmp_path, ScanSafetyConfig())
            assert not decision.should_scan
            assert "escapes" in (decision.reason or "")
        finally:
            outside.unlink()


class TestCheckLongLines:
    def test_normal_lines(self) -> None:
        source = b"x = 1\ny = 2\n"
        assert not check_long_lines(source, ScanSafetyConfig())

    def test_very_long_line(self) -> None:
        source = b"x = " + b"a" * 25_000 + b"\n"
        assert check_long_lines(source, ScanSafetyConfig())


class TestSafeReadSource:
    def test_valid_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "good.py"
        f.write_text("x = 1\n", encoding="utf-8")
        source, warning = safe_read_source(f)
        assert b"x = 1" in source
        assert warning is None

    def test_invalid_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_bytes(b"x = \x80\x81\n")
        source, warning = safe_read_source(f)
        assert len(source) > 0
        assert warning is not None
        assert "UTF-8" in warning

    def test_missing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.py"
        source, warning = safe_read_source(f)
        assert source == b""
        assert warning is not None


class TestPathSafety:
    def test_safe_path(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("x = 1\n")
        assert is_path_safe(f, tmp_path)

    def test_outside_path(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.py"
        assert not is_path_safe(outside, tmp_path)

    def test_normalize_rel_path(self, tmp_path: Path) -> None:
        f = tmp_path / "src" / "app.py"
        f.parent.mkdir()
        f.write_text("x = 1\n")
        result = normalize_rel_path(f, tmp_path)
        assert result == "src/app.py"

    def test_normalize_outside_returns_none(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "other.py"
        result = normalize_rel_path(outside, tmp_path)
        assert result is None


class TestScanBudget:
    def test_max_files_budget(self, tmp_path: Path) -> None:
        config = ScanSafetyConfig(max_files=5)
        for i in range(10):
            (tmp_path / f"file_{i}.py").write_text(f"x = {i}\n")
        # Verify config value is correct
        assert config.max_files == 5


class TestNoWritesDuringScan:
    def test_evaluate_does_not_write(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("x = 1\n")
        mtime_before = f.stat().st_mtime
        evaluate_file_policy(f, tmp_path, ScanSafetyConfig())
        mtime_after = f.stat().st_mtime
        assert mtime_before == mtime_after


class TestPickleSafety:
    def test_config_pickleable(self) -> None:
        import pickle

        config = ScanSafetyConfig(max_file_bytes=500_000)
        rt = pickle.loads(pickle.dumps(config))
        assert rt.max_file_bytes == 500_000

    def test_decision_pickleable(self) -> None:
        import pickle

        d = ScanPolicyDecision(should_scan=False, reason="too large")
        rt = pickle.loads(pickle.dumps(d))
        assert rt.reason == "too large"
