"""Tests for ImportResolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from airev_core.semantics.resolver import ImportResolver

if TYPE_CHECKING:
    from pathlib import Path


class TestPythonResolver:
    def test_stdlib_os(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("os") is True

    def test_stdlib_pathlib(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("pathlib") is True

    def test_stdlib_collections(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("collections") is True

    def test_stdlib_dotted(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("os.path") is True

    def test_workspace_module(self, tmp_path: Path) -> None:
        (tmp_path / "my_module.py").write_text("x = 1\n")
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("my_module") is True

    def test_workspace_package(self, tmp_path: Path) -> None:
        pkg = tmp_path / "my_package" / "sub"
        pkg.mkdir(parents=True)
        (tmp_path / "my_package" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("my_package") is True
        assert r.module_exists("my_package.sub") is True

    def test_nonexistent_package(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("definitely_not_a_real_package_xyz") is False

    def test_hallucinated_package(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("crypto_secure_hash") is False

    def test_installed_package(self, tmp_path: Path) -> None:
        # numpy should be installed in the test environment
        r = ImportResolver(str(tmp_path), "python")
        assert r.module_exists("numpy") is True

    def test_cache_works(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "python")
        r.module_exists("os")
        r.module_exists("os")
        assert r._cache["os"].exists is True


class TestJavaScriptResolver:
    def test_builtin_fs(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "javascript")
        assert r.module_exists("fs") is True

    def test_builtin_with_node_prefix(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "javascript")
        assert r.module_exists("node:path") is True

    def test_builtin_http(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "javascript")
        assert r.module_exists("http") is True

    def test_relative_import(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "javascript")
        assert r.module_exists("./utils") is True
        assert r.module_exists("../lib") is True

    def test_node_modules_package(self, tmp_path: Path) -> None:
        pkg = tmp_path / "node_modules" / "lodash"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text('{"name": "lodash"}')
        r = ImportResolver(str(tmp_path), "javascript")
        assert r.module_exists("lodash") is True

    def test_scoped_package(self, tmp_path: Path) -> None:
        pkg = tmp_path / "node_modules" / "@scope" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text('{"name": "@scope/pkg"}')
        r = ImportResolver(str(tmp_path), "javascript")
        assert r.module_exists("@scope/pkg") is True

    def test_nonexistent_package(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "javascript")
        assert r.module_exists("totally-fake-package-xyz") is False

    def test_typescript_resolver(self, tmp_path: Path) -> None:
        r = ImportResolver(str(tmp_path), "typescript")
        assert r.module_exists("fs") is True
        assert r.module_exists("fake-pkg") is False
