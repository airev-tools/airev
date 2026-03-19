# Contributing to airev

Thanks for your interest in contributing to airev! This guide covers everything you need to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/airev-tools/airev.git
cd airev

# Create a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Quality Gate

Run all checks before committing. Every one must pass:

```bash
ruff format .                              # Format code
ruff check .                               # Lint — must exit 0
mypy airev_core/ interfaces/ --strict      # Type check — must exit 0
pytest tests/ -v                           # Tests — must exit 0
```

## Adding a New Rule

1. Create the rule function in `airev_core/rules/common/` (or `language_specific/` if it only applies to one language).
2. Register it in `airev_core/rules/registry.py`.
3. Add test fixtures in `tests/fixtures/<language>/<rule_name>/`:
   - At least 2 true-positive files (code that SHOULD trigger)
   - At least 2 true-negative files (code that should NOT trigger)
   - 1 edge case file
4. Write tests in `tests/test_rules/test_<rule_name>.py`:
   - 1 snapshot test covering all fixtures
   - 1 integration test (source file → CLI → verify output)
5. Update `CHANGELOG.md` under `[Unreleased] > Added`.

## Commit Conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scanner): add hallucinated API detection rule
fix(parser): resolve false positive on re-exported types
docs(readme): add CLI usage examples
test(rules): add test cases for phantom import detection
chore(deps): bump tree-sitter to 0.22
```

## Branch Naming

```
feat/ast-parser
fix/import-resolution
docs/readme-update
test/add-phantom-import-tests
chore/deps-update
```

## Pull Requests

- Keep PRs small and focused — one logical change per PR.
- PR titles follow the same Conventional Commits format (we squash-merge).
- Fill out the PR template completely.
- All CI checks must pass before merge.

## Snapshot Tests

When rule behavior changes intentionally:

1. Run `pytest --snapshot-update`
2. Review **every** changed `.ambr` file in `tests/__snapshots__/`
3. Include updated snapshots in the same commit as the rule change

Never run `--snapshot-update` without reviewing each change.

## Architecture

Read `.claude/architecture.md` for the full architecture guide. Key principles:

- **Structure of Arrays (SoA)** — UAST nodes in numpy arrays, not Python objects
- **Dictionary jump tables** — O(1) dispatch, no match/case
- **Pure functions** — rules are `(arena, index, context) → findings`
- **Core/interface decoupling** — `airev_core/` never does I/O
