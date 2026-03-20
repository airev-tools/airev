"""Build workspace facts from filesystem inspection.

This is O(manifest count + root inspection), NOT O(full AST).
Runs once per scan before any parsing.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from airev_core.workspace.models import WorkspaceFacts


def build_workspace_facts(project_root: str) -> WorkspaceFacts:
    """Build workspace facts by inspecting the project root.

    This function reads manifests and inspects directory structure.
    It never executes code or imports anything from the target project.
    """
    root = Path(project_root)

    languages: set[str] = set()
    manifest_paths: list[str] = []
    first_party_prefixes: set[str] = set()
    third_party_deps: set[str] = set()
    python_module_roots: list[str] = []
    package_names: set[str] = set()
    ts_path_aliases: list[tuple[str, str]] = []
    has_lockfile = False

    # Detect Python manifests
    _collect_python_facts(
        root,
        languages,
        manifest_paths,
        first_party_prefixes,
        third_party_deps,
        python_module_roots,
        package_names,
    )

    # Detect JS/TS manifests
    _collect_js_facts(
        root,
        languages,
        manifest_paths,
        third_party_deps,
        ts_path_aliases,
        package_names,
    )

    # Detect lockfiles
    for lockfile in (
        "poetry.lock",
        "Pipfile.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "uv.lock",
    ):
        if (root / lockfile).is_file():
            has_lockfile = True
            break

    # Detect languages from file extensions if not already detected
    _detect_languages_from_files(root, languages)

    return WorkspaceFacts(
        project_root=str(root),
        languages=frozenset(languages),
        manifest_paths=tuple(manifest_paths),
        first_party_prefixes=frozenset(first_party_prefixes),
        third_party_dependencies=frozenset(third_party_deps),
        python_module_roots=tuple(python_module_roots),
        package_names=frozenset(package_names),
        ts_path_aliases=tuple(ts_path_aliases),
        has_lockfile=has_lockfile,
    )


def _collect_python_facts(
    root: Path,
    languages: set[str],
    manifest_paths: list[str],
    first_party_prefixes: set[str],
    third_party_deps: set[str],
    python_module_roots: list[str],
    package_names: set[str],
) -> None:
    """Collect Python-specific workspace facts."""
    # pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        languages.add("python")
        manifest_paths.append("pyproject.toml")
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project = data.get("project", {})
            name = project.get("name")
            if isinstance(name, str):
                package_names.add(name)
                # Infer first-party prefix from package name
                first_party_prefixes.add(name.replace("-", "_"))

            # Extract dependencies
            deps = project.get("dependencies", [])
            if isinstance(deps, list):
                for dep in deps:
                    if isinstance(dep, str):
                        # Extract package name (before any version specifier)
                        pkg = dep.split(">=")[0].split("<=")[0].split("==")[0]
                        pkg = pkg.split(">")[0].split("<")[0].split("~=")[0]
                        pkg = pkg.split("[")[0].strip()
                        if pkg:
                            third_party_deps.add(pkg)
        except (tomllib.TOMLDecodeError, OSError):
            pass

    # setup.cfg
    if (root / "setup.cfg").is_file():
        languages.add("python")
        manifest_paths.append("setup.cfg")

    # requirements.txt
    for req_file in ("requirements.txt", "requirements-dev.txt", "requirements.in"):
        if (root / req_file).is_file():
            languages.add("python")
            manifest_paths.append(req_file)
            _parse_requirements(root / req_file, third_party_deps)

    # Detect Python module roots
    # src/ layout
    src_dir = root / "src"
    if src_dir.is_dir():
        for child in src_dir.iterdir():
            if child.is_dir() and (child / "__init__.py").is_file():
                first_party_prefixes.add(child.name)
                python_module_roots.append(f"src/{child.name}")

    # Flat layout — packages at root with __init__.py
    for child in root.iterdir():
        if (
            child.is_dir()
            and child.name not in ("venv", ".venv", "env", "node_modules", ".git", "tests", "test")
            and not child.name.startswith(".")
            and (child / "__init__.py").is_file()
        ):
            first_party_prefixes.add(child.name)
            python_module_roots.append(child.name)


def _parse_requirements(req_path: Path, deps: set[str]) -> None:
    """Parse requirements.txt for package names."""
    try:
        for line in req_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg = line.split(">=")[0].split("<=")[0].split("==")[0]
            pkg = pkg.split(">")[0].split("<")[0].split("~=")[0]
            pkg = pkg.split("[")[0].strip()
            if pkg:
                deps.add(pkg)
    except OSError:
        pass


def _collect_js_facts(
    root: Path,
    languages: set[str],
    manifest_paths: list[str],
    third_party_deps: set[str],
    ts_path_aliases: list[tuple[str, str]],
    package_names: set[str],
) -> None:
    """Collect JS/TS-specific workspace facts."""
    # package.json
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        manifest_paths.append("package.json")
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            name = data.get("name")
            if isinstance(name, str):
                package_names.add(name)
                # Scoped packages: @scope/name
                if name.startswith("@"):
                    languages.add("javascript")
                else:
                    languages.add("javascript")

            # Dependencies
            for dep_key in ("dependencies", "devDependencies", "peerDependencies"):
                deps_dict = data.get(dep_key, {})
                if isinstance(deps_dict, dict):
                    third_party_deps.update(deps_dict.keys())
        except (json.JSONDecodeError, OSError):
            pass

    # tsconfig.json
    tsconfig = root / "tsconfig.json"
    if tsconfig.is_file():
        languages.add("typescript")
        manifest_paths.append("tsconfig.json")
        try:
            # tsconfig can have comments, try parsing as JSON
            raw = tsconfig.read_text(encoding="utf-8")
            # Strip single-line comments for basic parsing
            import re

            clean = re.sub(r"//.*", "", raw)
            data = json.loads(clean)
            compiler_options = data.get("compilerOptions", {})
            paths = compiler_options.get("paths", {})
            if isinstance(paths, dict):
                for alias, targets in paths.items():
                    if isinstance(targets, list) and targets:
                        ts_path_aliases.append((alias, str(targets[0])))
        except (json.JSONDecodeError, OSError):
            pass


def _detect_languages_from_files(root: Path, languages: set[str]) -> None:
    """Quick scan for language files if not already detected from manifests."""
    if languages:
        return

    # Only check top-level and one level deep to keep it cheap
    for child in root.iterdir():
        name = child.name
        if name.endswith(".py"):
            languages.add("python")
        elif name.endswith((".js", ".jsx")):
            languages.add("javascript")
        elif name.endswith((".ts", ".tsx")):
            languages.add("typescript")

        if child.is_dir() and not child.name.startswith("."):
            try:
                for grandchild in child.iterdir():
                    gname = grandchild.name
                    if gname.endswith(".py"):
                        languages.add("python")
                    elif gname.endswith((".js", ".jsx")):
                        languages.add("javascript")
                    elif gname.endswith((".ts", ".tsx")):
                        languages.add("typescript")
            except OSError:
                pass
