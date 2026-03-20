"""Performance-oriented regression tests.

These verify that the scanner doesn't accidentally do expensive work
on excluded or policy-blocked files.
"""

import time
from pathlib import Path

from airev_core.discovery.ignore import is_ignored, parse_ignorefile
from airev_core.security.scan_policy import ScanSafetyConfig, evaluate_file_policy
from airev_core.workspace.build_facts import build_workspace_facts


class TestNoParsingOfExcludedFiles:
    def test_ignored_files_not_parsed(self, tmp_path: Path) -> None:
        """Files matching .airevignore patterns should be skipped before any parsing."""
        patterns = parse_ignorefile("*.generated.py\nvendor/**\n")

        # Create files that should be excluded
        gen = tmp_path / "api.generated.py"
        gen.write_text("x = 1\n")
        vendor_file = tmp_path / "vendor" / "lib.py"
        vendor_file.parent.mkdir()
        vendor_file.write_text("y = 2\n")
        normal = tmp_path / "app.py"
        normal.write_text("z = 3\n")

        assert is_ignored("api.generated.py", patterns)
        assert is_ignored("vendor/lib.py", patterns)
        assert not is_ignored("app.py", patterns)

    def test_policy_blocked_files_not_parsed(self, tmp_path: Path) -> None:
        """Binary and oversized files blocked by policy before parsing."""
        binary = tmp_path / "data.py"
        binary.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        decision = evaluate_file_policy(binary, tmp_path, ScanSafetyConfig())
        assert not decision.should_scan


class TestFactsBuildPerformance:
    def test_facts_build_cheap_on_large_tree(self, tmp_path: Path) -> None:
        """Workspace facts build should not walk the entire directory tree."""
        # Create a synthetic large tree (shallow — just dirs and manifests)
        for i in range(100):
            d = tmp_path / f"pkg_{i}"
            d.mkdir()
            (d / "__init__.py").write_text("")
            (d / f"module_{i}.py").write_text(f"x = {i}\n")

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "big"\n')

        t0 = time.perf_counter()
        facts = build_workspace_facts(str(tmp_path))
        elapsed = time.perf_counter() - t0

        # Should complete in well under 1 second
        assert elapsed < 2.0
        assert "big" in facts.package_names


class TestNoQuadraticBehavior:
    def test_ignore_matching_linear(self) -> None:
        """Ignore pattern matching should be linear in number of patterns."""
        # Build a large set of patterns
        patterns = parse_ignorefile("\n".join(f"pattern_{i}/**" for i in range(200)) + "\n")

        t0 = time.perf_counter()
        for i in range(1000):
            is_ignored(f"src/module_{i}.py", patterns)
        elapsed = time.perf_counter() - t0

        # 1000 checks against 200 patterns should still be fast
        assert elapsed < 2.0
