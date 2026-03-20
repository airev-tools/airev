# airev GitHub Action

Detect semantic defects, phantom imports, hardcoded secrets, deprecated patterns, and other high-signal issues in AI-written and human-written code.

airev does **not** use generative AI to scan code. It is a deterministic static analysis tool.

## Quick start

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

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `path` | `.` | Path to scan |
| `format` | `sarif` | Output format: `terminal`, `json`, or `sarif` |
| `config` | | Path to `.airev.toml` config file |
| `rules` | | Run only this rule (e.g., `phantom-import`) |
| `lang` | | Scan only this language (`python`, `javascript`, `typescript`) |
| `fail-on-findings` | `true` | Fail the step when findings are present |

## Outputs

| Output | Description |
|--------|-------------|
| `findings-count` | Number of findings detected |
| `sarif-file` | Path to SARIF output file (when format is `sarif`) |
| `scan-status` | Scan outcome: `clean`, `findings`, or `error` |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Scan clean (no findings) |
| 1 | Findings detected (only when `fail-on-findings` is `true`) |
| 2 | Scanner or configuration error |
