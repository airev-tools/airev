"""Tests for workspace facts layer."""

import json
import pickle
from pathlib import Path

from airev_core.workspace.build_facts import build_workspace_facts


class TestPythonFacts:
    def test_src_layout(self, tmp_path: Path) -> None:
        """Python src/ layout infers first-party prefix."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "mypackage").mkdir()
        (tmp_path / "src" / "mypackage" / "__init__.py").write_text("")
        facts = build_workspace_facts(str(tmp_path))
        assert "mypackage" in facts.first_party_prefixes
        assert "src/mypackage" in facts.python_module_roots

    def test_flat_layout(self, tmp_path: Path) -> None:
        """Flat Python package layout infers module roots."""
        (tmp_path / "myapp").mkdir()
        (tmp_path / "myapp" / "__init__.py").write_text("")
        facts = build_workspace_facts(str(tmp_path))
        assert "myapp" in facts.first_party_prefixes
        assert "myapp" in facts.python_module_roots

    def test_pyproject_toml_deps(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-tool"\ndependencies = ["click>=8.0", "rich"]\n',
            encoding="utf-8",
        )
        facts = build_workspace_facts(str(tmp_path))
        assert "python" in facts.languages
        assert "click" in facts.third_party_dependencies
        assert "rich" in facts.third_party_dependencies
        assert "my-tool" in facts.package_names
        assert "my_tool" in facts.first_party_prefixes

    def test_requirements_txt(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask>=2.0\nrequests\n")
        facts = build_workspace_facts(str(tmp_path))
        assert "flask" in facts.third_party_dependencies
        assert "requests" in facts.third_party_dependencies


class TestJsFacts:
    def test_package_json(self, tmp_path: Path) -> None:
        pkg = {
            "name": "my-app",
            "dependencies": {"express": "^4.0", "lodash": "^4.0"},
            "devDependencies": {"jest": "^29"},
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        facts = build_workspace_facts(str(tmp_path))
        assert "javascript" in facts.languages
        assert "express" in facts.third_party_dependencies
        assert "jest" in facts.third_party_dependencies
        assert "my-app" in facts.package_names

    def test_tsconfig_path_aliases(self, tmp_path: Path) -> None:
        tsconfig = {
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@utils/*": ["src/utils/*"],
                    "@components/*": ["src/components/*"],
                },
            }
        }
        (tmp_path / "tsconfig.json").write_text(json.dumps(tsconfig), encoding="utf-8")
        facts = build_workspace_facts(str(tmp_path))
        assert "typescript" in facts.languages
        aliases = dict(facts.ts_path_aliases)
        assert "@utils/*" in aliases
        assert aliases["@utils/*"] == "src/utils/*"


class TestMixedMonorepo:
    def test_python_and_ts(self, tmp_path: Path) -> None:
        # Python part
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "backend"\n', encoding="utf-8")
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "__init__.py").write_text("")

        # TS part
        pkg = {"name": "frontend", "dependencies": {"react": "^18"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        facts = build_workspace_facts(str(tmp_path))
        assert "python" in facts.languages
        assert "javascript" in facts.languages
        assert "backend" in facts.first_party_prefixes
        assert "react" in facts.third_party_dependencies


class TestLockfileDetection:
    def test_poetry_lock(self, tmp_path: Path) -> None:
        (tmp_path / "poetry.lock").write_text("")
        facts = build_workspace_facts(str(tmp_path))
        assert facts.has_lockfile

    def test_package_lock(self, tmp_path: Path) -> None:
        (tmp_path / "package-lock.json").write_text("{}")
        facts = build_workspace_facts(str(tmp_path))
        assert facts.has_lockfile

    def test_no_lockfile(self, tmp_path: Path) -> None:
        facts = build_workspace_facts(str(tmp_path))
        assert not facts.has_lockfile


class TestNamespaceEdgeCases:
    def test_dir_without_init_not_first_party(self, tmp_path: Path) -> None:
        """Namespace packages (no __init__.py) handled conservatively."""
        (tmp_path / "loosedir").mkdir()
        (tmp_path / "loosedir" / "module.py").write_text("")
        facts = build_workspace_facts(str(tmp_path))
        assert "loosedir" not in facts.first_party_prefixes

    def test_hidden_dirs_excluded(self, tmp_path: Path) -> None:
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "__init__.py").write_text("")
        facts = build_workspace_facts(str(tmp_path))
        assert ".hidden" not in facts.first_party_prefixes


class TestPickleSafety:
    def test_facts_pickleable(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")
        facts = build_workspace_facts(str(tmp_path))
        roundtrip = pickle.loads(pickle.dumps(facts))
        assert roundtrip.project_root == facts.project_root
        assert roundtrip.package_names == facts.package_names
