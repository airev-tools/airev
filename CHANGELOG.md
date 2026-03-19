# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-03-20

### Added
- Inline suppression via `# airev: ignore[rule-id]` and `// airev: ignore[rule-id]` comments
- `.airevignore` file for gitignore-style path exclusion (glob, negation, directory-only patterns)
- Rule configuration via `.airev.toml` and `[tool.airev]` in `pyproject.toml`
- Graceful degradation — degraded confidence when `venv/` or `node_modules/` is missing
- SARIF 2.1.0 output format (`--format sarif`) for GitHub Code Scanning integration
- JSON output format (`--format json`)
- Scanner safety boundary — binary detection, file size limits, symlink safety, path traversal prevention
- `ScanSafetyConfig` for configurable safety limits
- `WorkspaceFacts` — lightweight, pickle-safe project context built from manifests (no code execution)
- Evidence-based confidence calibration from workspace facts (first-party, declared deps, lockfile)
- `LanguageCapabilities` registry for extensible per-language metadata
- Nuitka build script with PyInstaller fallback (`build/nuitka_build.py`)
- Performance benchmark suite (`benchmarks/benchmark_scan.py`)
- 36+ edge case tests covering config, safety, workspace, ignore, and output serialization

### Changed
- `ImportResolver.resolve_with_metadata()` now returns `ResolutionResult` with degraded state info
- Scan pipeline now applies safety policy before parsing and suppression after rule evaluation
- `LintContext` now carries optional `workspace_facts` for context-aware rule evaluation

## [0.1.0] — 2026-03-18

### Added
- `UastArena` — numpy Structure of Arrays storage for UAST nodes with bump allocation
- `StringTable` — interned string storage for identifier deduplication
- Python Tree-sitter parser with CST-to-UAST lowering
- JavaScript Tree-sitter parser with CST-to-UAST lowering
- TypeScript Tree-sitter parser with CST-to-UAST lowering
- `ParserRegistry` — auto-detects language from file extension (.py, .js, .jsx, .ts, .tsx)
- `airev scan` CLI command — full analysis pipeline with findings output
- `--lang` filter flag for scanning only a specific language
- `--format` flag (terminal/json) for output format selection
- `--rule` flag to run only a specific detection rule
- Exit code 1 when findings are detected
- Core data models: `Finding`, `Severity`, `Confidence`, `SourceSpan`, `CodeAction`
- UAST node type integer constants for dispatch table routing
- `SemanticModel` — pre-pass extraction of imports, definitions, and call sites
- `SemanticBuilder` — builds semantic models from UAST arena for Python and JS/TS
- `ImportResolver` — multi-strategy module existence checking (stdlib, workspace, venv, importlib)
- `LintContext` — frozen context bundle for rule evaluation
- `RuleRegistry` — rule registration and O(1) dispatch table construction
- `evaluate_file()` — pure-function linear scan engine with dictionary jump table dispatch
- `phantom-import` rule — detects imports of non-existent packages/modules
- `hallucinated-api` rule — detects calls to non-existent methods on real modules
- `FindingCollector` — deduplication and severity-ordered sorting of findings
- `hardcoded-secrets` rule — regex patterns, Shannon entropy, and false-positive suppression for API keys, tokens, passwords, and database URLs
- `deprecated-api` rule — curated deprecation database for Python stdlib, NumPy, and Node.js APIs with replacement suggestions
- `reinvented-internal` rule — detects AI-duplicated utility functions that already exist in the project
- `shannon_entropy()` pure function in `airev_core/heuristics/patterns.py`
- `DeprecatedAPI` dataclass and `DEPRECATED_APIS` curated database in deprecation_db.py
- `project_symbols` optional field on `LintContext` for cross-file analysis
- Project-wide symbol index built during scan pipeline (parse → index → evaluate)
- Comprehensive edge case tests for all rules in both Python and JS/TS
- CI coverage enforcement (70% minimum), snapshot integrity check, and pickle safety job
- `pytest-cov` added to dev dependencies
