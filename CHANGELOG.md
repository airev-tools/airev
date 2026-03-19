# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
