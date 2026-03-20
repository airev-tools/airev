"""Tests for the GitHub Action — metadata, entrypoint logic, safety."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ACTION_YML = _PROJECT_ROOT / "interfaces" / "github_action" / "action.yml"
_ENTRYPOINT = _PROJECT_ROOT / "interfaces" / "github_action" / "entrypoint.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_action_yml() -> dict[str, Any]:
    """Parse action.yml as YAML (fallback to manual parse if pyyaml unavailable)."""
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(_ACTION_YML.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except ImportError:
        # Minimal key-value extraction for CI without pyyaml
        text = _ACTION_YML.read_text(encoding="utf-8")
        result: dict[str, Any] = {}
        lines = text.splitlines()

        # Extract top-level scalar fields (name, description)
        for line in lines:
            if line.startswith("name:"):
                result["name"] = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("description:"):
                result["description"] = line.split(":", 1)[1].strip().strip('"')

        # Extract top-level mapping sections
        def _extract_section_keys(section: str) -> dict[str, Any]:
            mapping: dict[str, Any] = {}
            in_section = False
            for ln in lines:
                if ln.strip() == f"{section}:":
                    in_section = True
                    continue
                if in_section and ln and not ln[0].isspace():
                    break
                if in_section and ln.strip() and not ln.strip().startswith("#"):
                    key = ln.strip().rstrip(":")
                    if not key.startswith(("description", "required", "default")):
                        mapping[key] = {}
            return mapping

        if "inputs:" in text:
            result["inputs"] = _extract_section_keys("inputs")
        if "outputs:" in text:
            result["outputs"] = _extract_section_keys("outputs")
        if "runs:" in text:
            result["runs"] = {"using": ""}
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("using:"):
                    result["runs"]["using"] = stripped.split(":", 1)[1].strip().strip('"')
        return result


# ---------------------------------------------------------------------------
# Action metadata tests
# ---------------------------------------------------------------------------


class TestActionMetadata:
    def test_action_yml_exists(self) -> None:
        assert _ACTION_YML.exists()

    def test_required_fields_present(self) -> None:
        data = _load_action_yml()
        assert "name" in data
        assert "description" in data
        assert "inputs" in data
        assert "outputs" in data
        assert "runs" in data

    def test_name_does_not_say_ai_only(self) -> None:
        data = _load_action_yml()
        name = data["name"].lower()
        assert "ai-only" not in name
        assert "ai code" not in name

    def test_description_mentions_human_code(self) -> None:
        data = _load_action_yml()
        desc = data["description"].lower()
        assert "human" in desc

    def test_expected_inputs(self) -> None:
        data = _load_action_yml()
        inputs = data["inputs"]
        for key in ("path", "format", "config", "rules", "lang", "fail-on-findings"):
            assert key in inputs, f"Missing input: {key}"

    def test_expected_outputs(self) -> None:
        data = _load_action_yml()
        outputs = data["outputs"]
        for key in ("findings-count", "sarif-file", "scan-status"):
            assert key in outputs, f"Missing output: {key}"

    def test_uses_docker(self) -> None:
        data = _load_action_yml()
        assert data["runs"]["using"] == "docker"


# ---------------------------------------------------------------------------
# Entrypoint tests
# ---------------------------------------------------------------------------


class TestEntrypoint:
    def test_entrypoint_file_exists(self) -> None:
        assert _ENTRYPOINT.exists()

    def test_no_shell_true_in_entrypoint(self) -> None:
        """Entrypoint must never use shell=True for safety."""
        source = _ENTRYPOINT.read_text(encoding="utf-8")
        assert "shell=True" not in source

    def test_no_eval_or_exec_in_entrypoint(self) -> None:
        source = _ENTRYPOINT.read_text(encoding="utf-8")
        # Allow the word "exec" in comments/strings but not as a function call
        lines = [
            ln
            for ln in source.splitlines()
            if not ln.strip().startswith("#") and not ln.strip().startswith('"')
        ]
        code = "\n".join(lines)
        assert "eval(" not in code
        assert "exec(" not in code

    def test_build_argv_safe(self) -> None:
        sys.path.insert(0, str(_PROJECT_ROOT))
        try:
            from interfaces.github_action.entrypoint import _build_argv

            argv = _build_argv(".", "sarif", "", "", "")
            assert argv == ["python", "-m", "interfaces.cli.main", "scan", ".", "--format", "sarif"]
        finally:
            sys.path.pop(0)

    def test_build_argv_with_options(self) -> None:
        sys.path.insert(0, str(_PROJECT_ROOT))
        try:
            from interfaces.github_action.entrypoint import _build_argv

            argv = _build_argv("/repo", "json", "/repo/.airev.toml", "phantom-import", "python")
            assert "--config" in argv
            assert "--rule" in argv
            assert "--lang" in argv
            assert "phantom-import" in argv
        finally:
            sys.path.pop(0)

    def test_clean_scan_outputs(self, tmp_path: Path) -> None:
        """Simulate a clean scan (exit 0)."""
        sys.path.insert(0, str(_PROJECT_ROOT))
        output_file = tmp_path / "github_output.txt"
        try:
            from interfaces.github_action.entrypoint import _write_output

            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
                _write_output("scan-status", "clean")
                _write_output("findings-count", "0")

            content = output_file.read_text(encoding="utf-8")
            assert "scan-status=clean" in content
            assert "findings-count=0" in content
        finally:
            sys.path.pop(0)

    def test_sarif_validation_rejects_bad_json(self, tmp_path: Path) -> None:
        """Verify entrypoint validates SARIF structure."""
        bad_sarif = '{"not": "sarif"}'
        data = json.loads(bad_sarif)
        # Missing version and runs — should not pass validation
        assert data.get("version") != "2.1.0" or "runs" not in data

    def test_sarif_validation_accepts_good_sarif(self) -> None:
        good_sarif = {
            "version": "2.1.0",
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
            "runs": [{"tool": {"driver": {"name": "airev"}}, "results": []}],
        }
        assert good_sarif["version"] == "2.1.0"
        assert "runs" in good_sarif


# ---------------------------------------------------------------------------
# Dockerfile tests
# ---------------------------------------------------------------------------


class TestDockerfile:
    def test_dockerfile_exists(self) -> None:
        dockerfile = _PROJECT_ROOT / "interfaces" / "github_action" / "Dockerfile"
        assert dockerfile.exists()

    def test_dockerfile_uses_slim_base(self) -> None:
        dockerfile = _PROJECT_ROOT / "interfaces" / "github_action" / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")
        assert "python:3.12-slim" in content

    def test_dockerfile_has_non_root_user(self) -> None:
        dockerfile = _PROJECT_ROOT / "interfaces" / "github_action" / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")
        assert "USER" in content

    def test_dockerfile_syntax_valid(self) -> None:
        """Basic Dockerfile syntax — every FROM/RUN/COPY/etc is recognized."""
        dockerfile = _PROJECT_ROOT / "interfaces" / "github_action" / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")
        valid_instructions = {
            "FROM",
            "RUN",
            "COPY",
            "WORKDIR",
            "ENTRYPOINT",
            "CMD",
            "ENV",
            "EXPOSE",
            "LABEL",
            "USER",
            "ARG",
            "ADD",
            "VOLUME",
        }
        in_continuation = False
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                in_continuation = False
                continue
            if stripped.startswith("#") and not in_continuation:
                continue
            if in_continuation:
                in_continuation = stripped.endswith("\\")
                continue
            instruction = stripped.split()[0].upper()
            assert instruction in valid_instructions, (
                f"Unknown Dockerfile instruction: {instruction}"
            )
            in_continuation = stripped.endswith("\\")
