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

# Verify everything works
ruff check . && mypy airev_core/ interfaces/ --strict && pytest tests/ -v
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

1. Create the rule in `airev_core/rules/common/` (or `language_specific/` if language-specific).
2. Implement the `NodeRule` or `FileRule` protocol from `airev_core/rules/base.py`.
3. Register it in `interfaces/cli/commands/scan.py` in `_build_registry()`.
4. Add tests in `tests/test_rules/test_<rule_name>.py`:
   - At least 2 true-positive cases (code that SHOULD trigger)
   - At least 2 true-negative cases (code that should NOT trigger)
   - 1 edge case
   - 1 snapshot test covering all cases
5. Update `CHANGELOG.md` under `[Unreleased] > Added`.

### Rule requirements

- Rules **must be pure functions**: `(arena, index, context) → list[Finding]`
- No side effects, no global state, no I/O
- Use `@dataclass(slots=True, frozen=True)` for all data structures
- Use dictionary jump tables for dispatch — never `match/case` or `isinstance` chains
- `airev_core/` must never import from `interfaces/`

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

## Testing the GitHub Action Locally

```bash
# Validate action metadata
python -c "import yaml; yaml.safe_load(open('interfaces/github_action/action.yml'))"

# Run action tests
pytest tests/test_github_action/ -v
```

## Testing Packaging

```bash
# Build sdist + wheel
python -m build

# Smoke test the built package (PyPI name: airev-scanner, CLI: airev)
python -m venv /tmp/airev-test
/tmp/airev-test/bin/pip install dist/*.whl
/tmp/airev-test/bin/airev --version
/tmp/airev-test/bin/airev scan . --format json

# Validate install script syntax
bash -n build/install.sh
```

## Architecture

Key principles (see `.claude/architecture.md` for full details):

- **Structure of Arrays (SoA)** — UAST nodes in numpy arrays, not Python objects
- **Dictionary jump tables** — O(1) dispatch, no match/case
- **Pure functions** — rules are `(arena, index, context) → findings`
- **Core/interface decoupling** — `airev_core/` never does I/O
- **Frozen slotted dataclasses** — `@dataclass(slots=True, frozen=True)` for all non-arena data
