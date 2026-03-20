"""GitHub Action entrypoint — safe subprocess execution, no shell interpolation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile


def _write_output(name: str, value: str) -> None:
    """Write a value to $GITHUB_OUTPUT."""
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def _build_argv(
    path: str,
    fmt: str,
    config: str,
    rule: str,
    lang: str,
) -> list[str]:
    """Build a safe argv list for the airev CLI. No shell interpolation."""
    argv = ["python", "-m", "interfaces.cli.main", "scan", path, "--format", fmt]
    if config:
        argv.extend(["--config", config])
    if rule:
        argv.extend(["--rule", rule])
    if lang:
        argv.extend(["--lang", lang])
    return argv


def main() -> int:
    """Run airev scan and handle outputs for GitHub Actions."""
    if len(sys.argv) < 7:
        print(
            "Usage: entrypoint.py <path> <format> <config> <rules> <lang> <fail-on-findings>",
            file=sys.stderr,
        )
        _write_output("scan-status", "error")
        _write_output("findings-count", "0")
        return 2

    scan_path = sys.argv[1]
    output_format = sys.argv[2] or "sarif"
    config = sys.argv[3]
    rule = sys.argv[4]
    lang = sys.argv[5]
    fail_on_findings = sys.argv[6].lower() != "false"

    argv = _build_argv(scan_path, output_format, config, rule, lang)

    # Run the scan as a subprocess — safe argv list, no string interpolation
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        cwd="/app",
    )

    stdout = result.stdout
    stderr = result.stderr

    if stderr:
        print(stderr, file=sys.stderr)

    # Exit code semantics: 0 = clean, 1 = findings, >=2 = error
    if result.returncode >= 2:
        print(f"airev scanner failed (exit code {result.returncode})", file=sys.stderr)
        _write_output("scan-status", "error")
        _write_output("findings-count", "0")
        return 2

    # Parse findings count
    findings_count = 0
    if result.returncode == 1:
        # Findings were detected
        if output_format in ("json", "sarif"):
            try:
                data = json.loads(stdout)
                if output_format == "json":
                    findings_count = len(data) if isinstance(data, list) else 0
                elif output_format == "sarif":
                    runs = data.get("runs", [])
                    findings_count = len(runs[0]["results"]) if runs else 0
            except (json.JSONDecodeError, KeyError, IndexError):
                findings_count = 1  # At least one finding (exit code 1)
        else:
            findings_count = 1  # Terminal format, can't parse count reliably

    _write_output("findings-count", str(findings_count))

    # Handle SARIF output
    sarif_path = ""
    if output_format == "sarif" and stdout.strip():
        try:
            sarif_data = json.loads(stdout)
            # Validate minimal SARIF structure
            if sarif_data.get("version") == "2.1.0" and "runs" in sarif_data:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".sarif",
                    prefix="airev-",
                    dir="/tmp",
                    delete=False,
                    encoding="utf-8",
                ) as f:
                    json.dump(sarif_data, f)
                    sarif_path = f.name
                _write_output("sarif-file", sarif_path)
            else:
                print("Warning: SARIF output failed validation", file=sys.stderr)
        except json.JSONDecodeError:
            print("Warning: SARIF output is not valid JSON", file=sys.stderr)

    # Set scan status
    if result.returncode == 0:
        _write_output("scan-status", "clean")
        print("airev scan: no issues found")
    else:
        _write_output("scan-status", "findings")
        print(f"airev scan: {findings_count} finding(s) detected")

    # Print raw output for terminal format
    if output_format == "terminal" and stdout:
        print(stdout)

    # Determine exit code
    if result.returncode == 1 and fail_on_findings:
        return 1
    if result.returncode >= 2:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
