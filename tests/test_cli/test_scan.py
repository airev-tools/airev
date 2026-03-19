"""Tests for the airev scan CLI command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from click.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

from interfaces.cli.main import cli


class TestScanCommand:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_scan_with_python_and_ts_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("def hello(): pass\n")
        (tmp_path / "app.ts").write_text("const x: number = 1\n")
        result = self.runner.invoke(cli, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "2 files" in result.output
        assert "Python" in result.output
        assert "Typescript" in result.output

    def test_scan_empty_directory(self, tmp_path: Path) -> None:
        result = self.runner.invoke(cli, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "0 files" in result.output

    def test_scan_with_lang_filter(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("def hello(): pass\n")
        (tmp_path / "app.ts").write_text("const x = 1\n")
        result = self.runner.invoke(cli, ["scan", str(tmp_path), "--lang", "python"])
        assert result.exit_code == 0
        assert "1 files" in result.output or "1 Python" in result.output
        assert "Typescript" not in result.output

    def test_scan_skips_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}\n")
        (tmp_path / "main.py").write_text("def hello(): pass\n")
        result = self.runner.invoke(cli, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "1 files" in result.output or "1 Python" in result.output

    def test_scan_default_directory(self) -> None:
        result = self.runner.invoke(cli, ["scan"])
        # Exit code 0 (no findings) or 1 (findings in project) are both valid
        assert result.exit_code in (0, 1)

    def test_version_flag(self) -> None:
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_exit_code_1_on_findings(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_text("import fake_nonexistent_pkg_xyz\n")
        result = self.runner.invoke(cli, ["scan", str(tmp_path)])
        assert result.exit_code == 1
        assert "issue(s) found" in result.output

    def test_json_output_format(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_text("import fake_nonexistent_pkg_xyz\n")
        result = self.runner.invoke(cli, ["scan", str(tmp_path), "--format", "json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert len(data) >= 1
        assert data[0]["rule_id"] == "phantom-import"

    def test_rule_filter(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_text("import fake_nonexistent_pkg_xyz\n")
        # Filter to hallucinated-api only — phantom-import should not fire
        result = self.runner.invoke(cli, ["scan", str(tmp_path), "--rule", "hallucinated-api"])
        assert result.exit_code == 0
        assert "No issues found" in result.output

    def test_no_findings_clean_code(self, tmp_path: Path) -> None:
        (tmp_path / "clean.py").write_text("x = 1 + 2\nprint(x)\n")
        result = self.runner.invoke(cli, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "No issues found" in result.output
