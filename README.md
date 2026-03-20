# Airev

<p align="center">
  <strong>Catch code that looks valid, but is actually wrong.</strong>
</p>

<p align="center">
  Airev is a lightweight semantic code quality scanner for <strong>AI-written and human-written code</strong>.
  It detects high-signal defects by understanding code structure, symbols, imports, and project context —
  without using generative AI to review your code.
</p>

<p align="center">
  <a href="#why-airev">Why Airev?</a> •
  <a href="#what-airev-finds">What Airev finds</a> •
  <a href="#install">Install</a> •
  <a href="#usage">Usage</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#safety">Safety</a>
</p>

<p align="center">

![CI](https://img.shields.io/github/actions/workflow/status/airev-tools/airev/ci.yml?branch=main&label=CI)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/github/license/airev-tools/airev)
![Release](https://img.shields.io/github/v/release/airev-tools/airev?include_prereleases)
![Stars](https://img.shields.io/github/stars/airev-tools/airev?style=social)
![Issues](https://img.shields.io/github/issues/airev-tools/airev)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)
![Status](https://img.shields.io/badge/status-under%20active%20development-orange)

</p>

---

## Why Airev?

Modern code often looks correct before it is actually correct.

It may:
- pass formatting
- pass linting
- look reasonable in code review
- still fail because it references the wrong API, the wrong import, a deprecated interface, or a risky pattern that does not match the real codebase

That problem shows up in both **AI-written** and **human-written** code.

**Airev exists to catch that class of defect early** — the semantic, context-wrong, and high-risk issues that traditional style-focused tools often miss.

> Airev scans AI-written and human-written code, but it is **not** an AI reviewer or generative scanner.
> It is a deterministic static analysis tool.

---

## What Airev is

Airev is a **high-performance, multi-language static analysis engine** focused on finding defects such as hallucinated APIs, phantom imports, deprecated API usage, hardcoded secrets, inconsistent error handling, and copy-paste drift. It is built in Python and currently targets **Python, JavaScript, and TypeScript**.

It is designed to be:
- lightweight
- fast
- zero-config by default
- safe to run on real repositories
- extensible to more languages over time

### Current interfaces
- CLI
- GitHub Action
- SARIF output

---

## What Airev finds

Airev focuses on high-signal findings that matter in real repositories.

### Examples
- **Hallucinated APIs** — calls to methods or symbols that sound real but do not exist
- **Phantom imports** — imports that look plausible but do not resolve in the actual project
- **Deprecated API usage** — calls into interfaces that should no longer be used
- **Hardcoded secrets** — credential-like literals committed into source
- **Inconsistent error handling** — patterns that hide failures or apply error logic unevenly
- **Copy-paste drift** — near-duplicate logic that diverges in risky ways

### Example
```python
from analytics.client import AnalyticsClient

client = AnalyticsClient()
client.send_event_batch(events)  # plausible, but method does not exist
```

```ts
import { RetryManager } from "@/internal/payments/retry" // import path does not resolve
```

Airev is meant to complement:
- linters
- type checkers
- tests
- code review

It does **not** replace them.

---

## Why developers should try it

Airev is useful when you want a tool that:
- catches defects that are easy to miss in review
- works on both AI-assisted and manually written code
- stays fast enough for local runs and CI
- does not require a heavy setup to get started

If your codebase mixes speed, contributors, AI assistance, and changing internal APIs, this is the kind of gap Airev is built to cover.

---

## Install

### pip
```bash
pip install airev
```

### Docker
```bash
docker pull ghcr.io/airev-tools/airev:latest
```

### Native binary
Planned release assets will include platform-specific binaries for Linux and macOS.

---

## Usage

### Scan the current repository
```bash
airev scan .
```

### Scan only one language
```bash
airev scan . --lang python
```

### Exclude paths
```bash
airev scan . --exclude "tests/**"
```

### Emit SARIF
```bash
airev scan . --format sarif
```

### Run a single rule
```bash
airev scan . --rule hallucinated-api
```

The project's default philosophy is **zero-config**: auto-detect languages and work with a single command.

---

## Example output

```text
AIREV001 hallucinated-api
  File: services/analytics.py:18
  Symbol: AnalyticsClient.send_event_batch
  Message: Called method does not exist on resolved interface
  Confidence: high

AIREV014 phantom-import
  File: billing/worker.ts:3
  Symbol: @/internal/payments/retry
  Message: Imported module could not be resolved in project context
  Confidence: high

AIREV031 hardcoded-secret
  File: config/dev.js:7
  Message: Detected credential-like literal committed in source
  Confidence: high
```

---

## How Airev works

At a high level, Airev follows a deterministic pipeline:

1. Read source files
2. Parse into Tree-sitter CSTs
3. Lower into a unified internal representation
4. Build semantic context
5. Run pure-function rules
6. Emit structured findings

The architecture is designed around:
- data-oriented internals
- immutable analysis stages
- pure-function rule evaluation
- fast dispatch
- parallel scanning

The pure-function approach is inspired by architectural ideas popularized in systems like **JAX**: transform inputs into outputs cleanly, avoid side effects, and keep the pipeline predictable. In Airev, that principle helps keep scanning safe, testable, and non-invasive.

---

## Configuration

### `.airev.toml`

Create a `.airev.toml` in your project root to customize behavior:

```toml
# Exclude paths from scanning
exclude = ["vendor/**", "*.generated.py"]

# Configure individual rules
[rules]
phantom-import = "off"            # disable a rule
hardcoded-secrets = "warning"     # change severity

[rules.deprecated-api]
enabled = true
severity = "error"
```

Configuration can also live in `pyproject.toml` under `[tool.airev]`. If both files exist, `.airev.toml` takes precedence.

### `.airevignore`

Create a `.airevignore` file (gitignore syntax) to exclude files from scanning:

```
# Skip generated code
*.generated.py
*.generated.ts

# Skip vendored dependencies
vendor/**

# But keep this one
!vendor/internal.py
```

### Inline suppression

Suppress individual findings with inline comments:

```python
import foo  # airev: ignore[phantom-import]
```

```javascript
import { bar } from "./missing"  // airev: ignore[phantom-import]
```

---

## Output formats

### Terminal (default)
```bash
airev scan .
```

### JSON
```bash
airev scan . --format json
```

### SARIF 2.1.0
```bash
airev scan . --format sarif
```

SARIF output integrates with GitHub Code Scanning, VS Code SARIF Viewer, and other SARIF-compatible tools.

---

## Safety

Airev is designed as a **read-only** scanner with a strict safety boundary.

### What airev does NOT do

- **No code execution** — airev never imports, evaluates, or runs repository code
- **No repo mutation** — airev never writes, moves, or deletes any project files
- **No network access** — scanning is fully offline; no telemetry, no API calls
- **No autofix application** — findings are reported, not applied (autofix is planned for a future release)
- **No side effects during rule evaluation** — every rule is a pure function

### File safety policy

Before parsing any file, airev applies a safety policy that skips:

- **Binary files** — detected via magic bytes (ELF, PNG, JPEG, PDF, ZIP, etc.) and NUL byte ratio
- **Oversized files** — files exceeding the size limit (default: 1 MB) are skipped
- **Minified/generated files** — files with lines exceeding 20,000 characters are skipped
- **Symlinks pointing outside the project** — prevents path traversal attacks
- **Unsafe paths** — files that resolve outside the project root are rejected

### Degraded confidence

When airev cannot fully verify an import (e.g., missing `venv/` or `node_modules/`), findings are reported with **degraded confidence** instead of being silently dropped. The finding message indicates that the environment is incomplete, so you can distinguish between confirmed defects and uncertain results.

---

## Project status

Airev is under active development. The repo and workflow are being shaped with release discipline, CI quality gates, changelog/versioning, and GitHub-native distribution in mind.

If the problem this solves is familiar, try it, open an issue, and star the repo to follow the project.

## License

[MIT](LICENSE)
