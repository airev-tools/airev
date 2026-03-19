"""Import resolver — determines if imported modules actually exist.

Resolution is strictly read-only: it checks file/directory existence but never
executes imported code.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from airev_core.semantics.stdlib_modules import (
    NODE_BUILTIN_MODULES,
    PYTHON_STDLIB_MODULES,
)


class ResolutionResult:
    """Result of module resolution with confidence metadata."""

    __slots__ = ("exists", "degraded", "reason")

    def __init__(self, exists: bool, degraded: bool = False, reason: str = "") -> None:
        self.exists = exists
        self.degraded = degraded
        self.reason = reason


class ImportResolver:
    """Resolves import statements to determine if packages/modules exist."""

    __slots__ = ("_project_root", "_language", "_cache", "_degraded")

    def __init__(self, project_root: str, language: str) -> None:
        self._project_root = Path(project_root)
        self._language = language
        self._cache: dict[str, ResolutionResult] = {}
        self._degraded = self._detect_degraded_env()

    @property
    def is_degraded(self) -> bool:
        """True if the environment is incomplete (no venv, no node_modules)."""
        return self._degraded

    def _detect_degraded_env(self) -> bool:
        """Check if the environment is missing expected dependency infrastructure."""
        if self._language == "python":
            # No venv directory found
            for venv_dir in ("venv", ".venv", "env"):
                if (self._project_root / venv_dir).is_dir():
                    return False
            return True
        if self._language in ("javascript", "typescript"):
            # No node_modules directory found
            return not (self._project_root / "node_modules").is_dir()
        return False

    def module_exists(self, module_name: str) -> bool:
        """Return True if the module can be resolved to a real package/file."""
        result = self.resolve_with_metadata(module_name)
        return result.exists

    def resolve_with_metadata(self, module_name: str) -> ResolutionResult:
        """Resolve a module and return result with degradation metadata."""
        if module_name in self._cache:
            return self._cache[module_name]

        result = self._resolve(module_name)
        self._cache[module_name] = result
        return result

    def _resolve(self, module_name: str) -> ResolutionResult:
        if self._language == "python":
            return self._resolve_python(module_name)
        if self._language in ("javascript", "typescript"):
            return self._resolve_js(module_name)
        return ResolutionResult(exists=True)

    # ── Python resolution ──────────────────────────────────────────

    def _resolve_python(self, module_name: str) -> ResolutionResult:
        top_level = module_name.split(".")[0]

        # 1. Standard library
        if top_level in PYTHON_STDLIB_MODULES:
            return ResolutionResult(exists=True)

        # 2. Workspace — check project root for .py file or package dir
        if self._check_python_workspace(module_name):
            return ResolutionResult(exists=True)

        # 3. Virtual environment — scan site-packages
        if self._check_python_venv(top_level):
            return ResolutionResult(exists=True)

        # 4. Installed packages fallback — importlib.util.find_spec
        if self._check_python_installed(module_name):
            return ResolutionResult(exists=True)

        # Not found — mark as degraded if no venv present
        if self._degraded:
            return ResolutionResult(
                exists=False,
                degraded=True,
                reason="no virtual environment found",
            )
        return ResolutionResult(exists=False)

    def _check_python_workspace(self, module_name: str) -> bool:
        """Check if module exists as a file/package in the project root."""
        rel_path = module_name.replace(".", "/")
        root = self._project_root

        # Check for module.py
        if (root / f"{rel_path}.py").is_file():
            return True
        # Check for package/__init__.py
        return (root / rel_path / "__init__.py").is_file()

    def _check_python_venv(self, top_level: str) -> bool:
        """Check common venv directories for the package."""
        for venv_dir in ("venv", ".venv", "env"):
            venv_path = self._project_root / venv_dir
            if not venv_path.is_dir():
                continue
            # Search for site-packages
            for site_packages in venv_path.rglob("site-packages"):
                if not site_packages.is_dir():
                    continue
                # Check for package directory or .py file
                if (site_packages / top_level).is_dir():
                    return True
                if (site_packages / f"{top_level}.py").is_file():
                    return True
                # Check dist-info for package name mapping
                for dist_info in site_packages.glob(f"{top_level}*.dist-info"):
                    if dist_info.is_dir():
                        return True
        return False

    def _check_python_installed(self, module_name: str) -> bool:
        """Use importlib as a last-resort check."""
        try:
            spec = importlib.util.find_spec(module_name)
            return spec is not None
        except (ModuleNotFoundError, ValueError):
            return False

    # ── JavaScript/TypeScript resolution ───────────────────────────

    def _resolve_js(self, module_name: str) -> ResolutionResult:
        # Handle node: prefix
        bare = module_name.removeprefix("node:")

        # 1. Node.js built-ins
        if bare in NODE_BUILTIN_MODULES:
            return ResolutionResult(exists=True)

        # 2. Relative imports — always assume valid (hard to resolve without
        #    knowing the importing file's path)
        if module_name.startswith("./") or module_name.startswith("../"):
            return ResolutionResult(exists=True)

        # 3. node_modules lookup
        if self._check_node_modules(module_name):
            return ResolutionResult(exists=True)

        # Not found — mark as degraded if no node_modules present
        if self._degraded:
            return ResolutionResult(
                exists=False,
                degraded=True,
                reason="no node_modules directory found",
            )
        return ResolutionResult(exists=False)

    def _check_node_modules(self, module_name: str) -> bool:
        """Walk up from project root checking node_modules."""
        # Handle scoped packages: @scope/pkg → node_modules/@scope/pkg
        current = self._project_root
        while True:
            nm_path = current / "node_modules" / module_name
            if nm_path.is_dir():
                # Check for package.json
                if (nm_path / "package.json").is_file():
                    return True
                # Some packages don't have package.json at top level
                return True
            # Also check for a direct .js file (rare but possible)
            for ext in (".js", ".mjs", ".cjs"):
                if (current / "node_modules" / f"{module_name}{ext}").is_file():
                    return True

            parent = current.parent
            if parent == current:
                break
            current = parent

        return False
