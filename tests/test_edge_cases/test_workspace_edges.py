"""Edge case tests for workspace facts and resolver."""

import json
from pathlib import Path

from airev_core.semantics.resolver import ImportResolver
from airev_core.workspace.build_facts import build_workspace_facts


class TestMonorepoFacts:
    def test_multiple_package_jsons(self, tmp_path: Path) -> None:
        """Monorepo with multiple package.json files — root is used."""
        root_pkg = {"name": "root", "dependencies": {"express": "^4"}}
        (tmp_path / "package.json").write_text(json.dumps(root_pkg))
        # Sub-package
        sub = tmp_path / "packages" / "sub"
        sub.mkdir(parents=True)
        sub_pkg = {"name": "sub", "dependencies": {"lodash": "^4"}}
        (sub / "package.json").write_text(json.dumps(sub_pkg))

        facts = build_workspace_facts(str(tmp_path))
        assert "express" in facts.third_party_dependencies
        # Sub-package deps are NOT included (only root manifest scanned)
        assert "lodash" not in facts.third_party_dependencies

    def test_multiple_python_package_roots(self, tmp_path: Path) -> None:
        for pkg in ("auth", "api"):
            (tmp_path / pkg).mkdir()
            (tmp_path / pkg / "__init__.py").write_text("")
        facts = build_workspace_facts(str(tmp_path))
        assert "auth" in facts.first_party_prefixes
        assert "api" in facts.first_party_prefixes

    def test_ts_path_aliases_with_wildcards(self, tmp_path: Path) -> None:
        tsconfig = {"compilerOptions": {"paths": {"@/*": ["src/*"], "@lib/*": ["lib/*"]}}}
        (tmp_path / "tsconfig.json").write_text(json.dumps(tsconfig))
        facts = build_workspace_facts(str(tmp_path))
        alias_dict = dict(facts.ts_path_aliases)
        assert "@/*" in alias_dict
        assert "@lib/*" in alias_dict

    def test_namespace_package_layout(self, tmp_path: Path) -> None:
        """Namespace packages (no __init__.py) not treated as first-party."""
        (tmp_path / "namespace_pkg").mkdir()
        (tmp_path / "namespace_pkg" / "sub.py").write_text("x = 1")
        facts = build_workspace_facts(str(tmp_path))
        assert "namespace_pkg" not in facts.first_party_prefixes

    def test_vendored_code_directory(self, tmp_path: Path) -> None:
        """Vendored code should not be treated as first-party."""
        (tmp_path / "vendor").mkdir()
        # Vendor doesn't have __init__.py typically
        (tmp_path / "vendor" / "lib.py").write_text("x = 1")
        facts = build_workspace_facts(str(tmp_path))
        assert "vendor" not in facts.first_party_prefixes


class TestResolverEdges:
    def test_import_shadowing_by_local_file(self, tmp_path: Path) -> None:
        """Local file shadows a stdlib module — resolver finds the local one."""
        (tmp_path / "json.py").write_text("x = 1")
        resolver = ImportResolver(str(tmp_path), "python")
        # Should resolve via workspace check (local json.py)
        assert resolver.module_exists("json")

    def test_missing_lockfiles_with_manifests(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        facts = build_workspace_facts(str(tmp_path))
        assert not facts.has_lockfile
        assert "pyproject.toml" in facts.manifest_paths
