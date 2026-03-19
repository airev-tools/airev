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
- `airev scan` CLI command — walks directory, parses supported files, prints summary
- `--lang` filter flag for scanning only a specific language
- Core data models: `Finding`, `Severity`, `Confidence`, `SourceSpan`, `CodeAction`
- UAST node type integer constants for dispatch table routing
