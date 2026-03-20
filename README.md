# airev

**Catch code that looks valid, but is actually wrong.**

![CI](https://img.shields.io/github/actions/workflow/status/airev-tools/airev/ci.yml?branch=main&label=CI)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/github/license/airev-tools/airev)

Fast semantic code quality scanner for AI-written and human-written code. airev does **not** use generative AI to scan code — it is a deterministic static analysis tool.

---

## Demo

```text
 File     │ Line │ Rule             │ Severity │ Message
──────────┼──────┼──────────────────┼──────────┼─────────────────────────────────────────
 app.py   │   3  │ phantom-import   │ error    │ Module 'analytics.client' not found
 app.py   │   6  │ hallucinated-api │ error    │ 'Client.send_event_batch' does not exist
 config.js│   7  │ hardcoded-secret │ warning  │ Possible API key in string literal
```

---

## What it catches

| Rule | Description |
|------|-------------|
| `phantom-import` | Imports of packages or modules that don't exist in the project |
| `hallucinated-api` | Calls to methods/functions that don't exist on real packages |
| `deprecated-api` | Usage of deprecated APIs from Python stdlib, NumPy, Node.js |
| `hardcoded-secrets` | API keys, tokens, passwords left in source code |
| `reinvented-internal` | AI-duplicated utility functions that already exist in the project |

Languages: **Python**, **JavaScript**, **TypeScript**

---

## Install

### pip (recommended)
```bash
pip install airev
```

### Docker
```bash
docker pull ghcr.io/airev-tools/airev:latest
docker run --rm -v "$(pwd):/repo" ghcr.io/airev-tools/airev /repo
```

### Native binary (Linux, macOS)
```bash
curl -fsSL https://raw.githubusercontent.com/airev-tools/airev/main/build/install.sh | bash
```

Binaries are available for Linux x86_64, macOS x86_64, and macOS ARM64. If your platform is unsupported, use `pip install airev`.

---

## Usage

```bash
# Scan the current directory
airev scan .

# Scan only Python files
airev scan . --lang python

# Output as JSON
airev scan . --format json

# Output as SARIF (for GitHub Code Scanning)
airev scan . --format sarif

# Run a single rule
airev scan . --rule phantom-import

# Check version
airev --version
```

Zero-config by default: auto-detects languages, scans all supported files.

---

## GitHub Action

```yaml
name: airev
on:
  pull_request:

jobs:
  airev:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4

      - name: Run airev
        id: airev
        uses: airev-tools/airev@v0.2.0
        with:
          format: sarif

      - name: Upload SARIF
        if: always() && steps.airev.outputs.sarif-file != ''
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ${{ steps.airev.outputs.sarif-file }}
```

See [Action documentation](interfaces/github_action/README.md) for all inputs and outputs.

---

## Configuration

### `.airev.toml`

```toml
exclude = ["vendor/**", "*.generated.py"]

[rules]
phantom-import = "off"
hardcoded-secrets = "warning"

[rules.deprecated-api]
enabled = true
severity = "error"
```

Also supports `[tool.airev]` in `pyproject.toml`. If both exist, `.airev.toml` takes precedence.

### `.airevignore`

Gitignore-style file exclusion:

```
*.generated.py
vendor/**
!vendor/internal.py
```

### Inline suppression

```python
import foo  # airev: ignore[phantom-import]
```

---

## How it works

1. Read source files (with safety checks: binary/size/symlink filtering)
2. Parse with Tree-sitter (error-tolerant, multi-language)
3. Lower into a unified AST stored in numpy arrays (Structure of Arrays)
4. Build semantic context (imports, symbols, workspace facts)
5. Evaluate pure-function rules via dictionary jump-table dispatch
6. Emit findings as terminal output, JSON, or SARIF

All analysis is read-only. Rules are pure functions with no side effects. No code is ever executed or imported from the scanned repository.

---

## Safety

- **No code execution** — never imports, evaluates, or runs repository code
- **No repo mutation** — never writes, moves, or deletes project files
- **No network access** — fully offline, no telemetry
- **Binary/oversized/minified files** — automatically skipped before parsing
- **Symlinks outside project** — rejected to prevent path traversal
- **Missing dependencies** — reported as degraded confidence, not silently dropped

---

## License

[MIT](LICENSE)
