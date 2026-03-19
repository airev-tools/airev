"""Tests for graceful degradation when dependencies are missing."""

from pathlib import Path

from airev_core.semantics.resolver import ImportResolver


class TestPythonDegradation:
    def test_degraded_without_venv(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "python")
        assert resolver.is_degraded

    def test_not_degraded_with_venv(self, tmp_path: Path) -> None:
        (tmp_path / "venv").mkdir()
        resolver = ImportResolver(str(tmp_path), "python")
        assert not resolver.is_degraded

    def test_resolution_metadata_degraded(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "python")
        result = resolver.resolve_with_metadata("nonexistent_package")
        assert not result.exists
        assert result.degraded
        assert "virtual environment" in result.reason

    def test_stdlib_still_resolves_when_degraded(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "python")
        assert resolver.module_exists("os")
        assert resolver.module_exists("sys")

    def test_workspace_module_resolves_when_degraded(self, tmp_path: Path) -> None:
        (tmp_path / "mymodule.py").write_text("x = 1\n")
        resolver = ImportResolver(str(tmp_path), "python")
        assert resolver.module_exists("mymodule")


class TestJsDegradation:
    def test_degraded_without_node_modules(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "javascript")
        assert resolver.is_degraded

    def test_not_degraded_with_node_modules(self, tmp_path: Path) -> None:
        (tmp_path / "node_modules").mkdir()
        resolver = ImportResolver(str(tmp_path), "javascript")
        assert not resolver.is_degraded

    def test_resolution_metadata_degraded_js(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "javascript")
        result = resolver.resolve_with_metadata("express")
        assert not result.exists
        assert result.degraded
        assert "node_modules" in result.reason

    def test_builtins_still_resolve(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "javascript")
        assert resolver.module_exists("fs")
        assert resolver.module_exists("path")

    def test_relative_imports_still_resolve(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "javascript")
        assert resolver.module_exists("./utils")


class TestResolutionResultCache:
    def test_cache_hit(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "python")
        # First call populates cache
        r1 = resolver.resolve_with_metadata("os")
        # Second call should return cached result
        r2 = resolver.resolve_with_metadata("os")
        assert r1 is r2
