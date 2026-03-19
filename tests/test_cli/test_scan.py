"""Tests for the airev scan CLI command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

from interfaces.cli.main import cli


class TestScanCommand:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_scan_with_python_and_ts_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("import os\ndef hello(): pass\n")
        (tmp_path / "app.ts").write_text('import express from "express"\n')
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
        (tmp_path / "main.py").write_text("import os\n")
        (tmp_path / "app.ts").write_text("const x = 1\n")
        result = self.runner.invoke(cli, ["scan", str(tmp_path), "--lang", "python"])
        assert result.exit_code == 0
        assert "1 files" in result.output or "1 Python" in result.output
        assert "Typescript" not in result.output

    def test_scan_skips_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}\n")
        (tmp_path / "main.py").write_text("import os\n")
        result = self.runner.invoke(cli, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "1 files" in result.output or "1 Python" in result.output

    def test_scan_default_directory(self) -> None:
        result = self.runner.invoke(cli, ["scan"])
        assert result.exit_code == 0

    def test_version_flag(self) -> None:
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
