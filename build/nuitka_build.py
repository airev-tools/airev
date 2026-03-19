#!/usr/bin/env python3
"""Nuitka build script for airev native binary.

Produces a standalone single-file binary that bundles:
- Python runtime
- Tree-sitter grammars (Python, JS, TS)
- All airev_core and interfaces code

Usage:
    python build/nuitka_build.py

Output:
    dist/airev  (or dist/airev.exe on Windows)

If Nuitka is unavailable, falls back to PyInstaller.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DIST_DIR = _PROJECT_ROOT / "dist"
_ENTRY_POINT = _PROJECT_ROOT / "interfaces" / "cli" / "main.py"


def _find_tree_sitter_libs() -> list[str]:
    """Locate tree-sitter grammar shared libraries for inclusion."""
    include_args: list[str] = []
    for pkg_name in ("tree_sitter_python", "tree_sitter_javascript", "tree_sitter_typescript"):
        try:
            mod = __import__(pkg_name)
            pkg_dir = Path(mod.__file__).parent if mod.__file__ else None
            if pkg_dir and pkg_dir.is_dir():
                include_args.extend(["--include-data-dir=" + str(pkg_dir) + "=" + pkg_name])
        except ImportError:
            print(f"  Warning: {pkg_name} not found, binary may not work for that language")
    return include_args


def _build_nuitka() -> bool:
    """Try building with Nuitka. Returns True on success."""
    if shutil.which("nuitka3") is None and shutil.which("nuitka") is None:
        print("Nuitka not found. Install with: pip install nuitka")
        return False

    nuitka_cmd = "nuitka3" if shutil.which("nuitka3") else "nuitka"
    ts_args = _find_tree_sitter_libs()

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={_DIST_DIR}",
        "--output-filename=airev",
        "--follow-imports",
        "--include-package=airev_core",
        "--include-package=interfaces",
        "--include-package=tree_sitter",
        *ts_args,
        "--assume-yes-for-downloads",
        str(_ENTRY_POINT),
    ]

    print(f"Building with Nuitka: {' '.join(cmd[:6])}...")
    result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    return result.returncode == 0


def _build_pyinstaller() -> bool:
    """Fallback: build with PyInstaller."""
    if shutil.which("pyinstaller") is None:
        print("PyInstaller not found. Install with: pip install pyinstaller")
        return False

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name=airev",
        f"--distpath={_DIST_DIR}",
        "--clean",
        str(_ENTRY_POINT),
    ]

    print(f"Building with PyInstaller (fallback): {' '.join(cmd[:5])}...")
    result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    return result.returncode == 0


def main() -> None:
    """Build airev binary, trying Nuitka first then PyInstaller."""
    _DIST_DIR.mkdir(exist_ok=True)

    system = platform.system().lower()
    arch = platform.machine().lower()
    print(f"Building airev for {system}-{arch}")
    print(f"Entry point: {_ENTRY_POINT}")
    print(f"Output dir: {_DIST_DIR}\n")

    if _build_nuitka():
        print(f"\nBuild successful! Binary at: {_DIST_DIR}/airev")
        return

    print("\nNuitka build failed or unavailable. Trying PyInstaller fallback...\n")

    if _build_pyinstaller():
        print(f"\nPyInstaller build successful! Binary at: {_DIST_DIR}/airev")
        return

    print("\nBoth Nuitka and PyInstaller failed.")
    print("To build manually, install one of:")
    print("  pip install nuitka")
    print("  pip install pyinstaller")
    sys.exit(1)


if __name__ == "__main__":
    main()
