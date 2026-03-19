# airev

**AI Code Quality Scanner — catches what copilots miss.**

You are contributing to `airev-tools/airev`. Read and follow ALL instruction files before writing any code.

## Skill Files (MANDATORY)

- [.claude/architecture.md](.claude/architecture.md) — Code architecture, data structures, design patterns, performance requirements, project structure, dependencies, and coding standards.
- [.claude/github-workflow.md](.claude/github-workflow.md) — Git branching, commit conventions, PR standards, CI requirements, release workflow, and testing requirements.

**Never skip reading these files. They define how this project operates.**

## Project Summary

airev is a static analysis engine that detects defects specific to AI-generated code:

- **Phantom imports** — imports of packages/modules that don't exist
- **Hallucinated APIs** — calls to methods/functions that don't exist on real packages
- **Deprecated APIs** — usage of outdated APIs from older library versions
- **Hardcoded secrets** — API keys, tokens, passwords left in source code
- **Inconsistent error handling** — mixed patterns (try/catch vs .catch vs null returns) in one file
- **Copy-paste drift** — near-duplicate code blocks from iterative AI prompting

## Core Architecture Principles

1. **Structure of Arrays (SoA)** — UAST nodes stored in parallel numpy arrays (`UastArena`), not Python objects. Nodes are integer indices. This gives contiguous memory access and ~10x traversal speed.
2. **Dictionary jump tables** — O(1) dispatch mapping integer node types to rule functions. Never use match/case or isinstance chains.
3. **Pure functions** — Every rule is `(arena, index, context) → list[findings]`. No side effects. No global state. No mutation during evaluation.
4. **`@dataclass(slots=True, frozen=True)`** — For all non-arena data structures. 63% memory reduction over standard classes.
5. **Core/interface decoupling** — `airev_core/` knows nothing about files, terminals, or CLI. It receives bytes and returns findings.

## Tech Stack

- **Language:** Python 3.12+
- **Parsing:** Tree-sitter (error-tolerant, multi-language, C-backed)
- **Memory:** numpy arrays (contiguous, cache-friendly, GC-invisible)
- **Heuristics:** datasketch (MinHash), numpy stride tricks (Winnowing)
- **Parallelism:** loky (robust process pools)
- **CLI:** click + rich
- **Testing:** pytest + syrupy (snapshot testing)
- **Linting:** ruff (format + lint) + mypy (strict type checking)
- **Distribution:** Nuitka (AOT binary), Docker, pip

## Key Commands

```bash
# Quality gate (run before every commit)
ruff format .
ruff check .
mypy airev_core/ interfaces/ --strict
pytest tests/ -v

# Snapshot tests (when rule behavior changes intentionally)
pytest --snapshot-update    # then review EVERY changed .ambr file

# Run the tool
airev scan .
airev scan . --lang python
airev scan . --format sarif
airev scan . --fix
```

## What NOT To Do

- Never commit directly to `main`
- Never use `@dataclass` without `slots=True`
- Never use match/case or singledispatch for node routing
- Never store UAST nodes as Python objects in lists (use the numpy arena)
- Never print from `airev_core/` (return data, let interfaces format it)
- Never use global mutable state
- Never skip tests when adding a rule
- Never run `--snapshot-update` without reviewing every change

## Work Habits (MANDATORY)

### Commit Frequency
- **Commit after every meaningful unit of work.** A "unit" is one of:
  - A single file created with working logic
  - A single function/class implemented and passing its tests
  - A bug fix
  - A test file added
  - A config or docs update
- **NEVER accumulate more than ~100 lines of uncommitted changes.** If you've written more than that without committing, stop and commit now.
- **NEVER batch multiple unrelated changes into one commit.** If you built a parser AND a rule, that's two commits minimum.

### Progress Updates
- **After every commit**, print a short status update:
```
  ✅ COMMITTED: feat(arena): implement UastArena with bump allocation
  📁 Files changed: airev_core/arena/uast_arena.py, tests/test_arena/test_uast_arena.py
  📊 Progress: [Phase 1] 2/6 tasks complete
  🔜 Next: Tree-sitter Python parser
```
- **After completing a phase or major milestone**, print a summary table:
```
  ══════════════════════════════════════════
  PHASE 1 COMPLETE — Foundation
  ══════════════════════════════════════════
  ✅ UastArena + StringTable
  ✅ Python parser (CST → Arena)
  ✅ JS/TS parser (CST → Arena)
  ✅ Parser registry (auto-detect)
  ✅ Basic CLI (airev scan .)
  ──────────────────────────────────────────
  Total commits: 8
  Tests passing: 14
  Next phase: Phase 2 — First Rules
  ══════════════════════════════════════════
```

### Reverting Safety
- Every commit should leave the project in a **working state** — tests pass, lint passes. Never commit broken code.
- If a task requires multiple steps that temporarily break things, use a local work-in-progress approach but ensure the final commit for each step is green.
- Before starting any risky refactor, tell me what you're about to do and confirm I want to proceed.