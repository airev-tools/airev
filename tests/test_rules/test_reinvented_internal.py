"""Tests for the reinvented-internal detection rule."""

import pickle
from pathlib import Path

from airev_core.parsers.python_parser import PythonParser
from airev_core.rules.common.reinvented_internal import ReinventedInternalRule
from airev_core.rules.registry import RuleRegistry, evaluate_file
from airev_core.semantics.builder import SemanticBuilder
from airev_core.semantics.context import LintContext, ProjectSymbols
from airev_core.semantics.resolver import ImportResolver
from airev_core.semantics.symbols import DefinedSymbol


def _build_project_symbols(
    file_sources: dict[str, bytes],
) -> tuple[dict[str, tuple[object, ...]], ProjectSymbols]:
    """Parse multiple files and build a project-wide symbol index."""
    parser = PythonParser()
    builder = SemanticBuilder()
    parsed: dict[str, tuple[object, ...]] = {}
    project_symbols: ProjectSymbols = {}

    for fpath, source in file_sources.items():
        arena = parser.parse(source)
        semantic = builder.build(arena, "python")
        parsed[fpath] = (arena, semantic, source)
        for defn in semantic.definitions:
            project_symbols.setdefault(defn.name, []).append((fpath, defn))

    return parsed, project_symbols


def _run_rule(
    source: bytes,
    file_path: str,
    project_symbols: ProjectSymbols,
    tmp_path: Path,
) -> list[object]:
    parser = PythonParser()
    arena = parser.parse(source)
    builder = SemanticBuilder()
    semantic = builder.build(arena, "python")
    resolver = ImportResolver(str(tmp_path), "python")
    ctx = LintContext(
        arena=arena,
        semantic=semantic,
        file_path=file_path,
        language="python",
        source=source,
        resolver=resolver,
        project_symbols=project_symbols,
    )
    rule = ReinventedInternalRule()
    reg = RuleRegistry()
    reg.register_file_rule(rule)
    table = reg.build_dispatch_table("python")
    file_rules = reg.get_file_rules("python")
    return evaluate_file(arena, table, file_rules, ctx)


class TestReinventedInternal:
    """True positive tests — function exists in utility dir."""

    def test_duplicate_in_utils(self, tmp_path: Path) -> None:
        """Function in service file duplicates one in utils/ → SHOULD flag."""
        utils_source = b"def format_date(d):\n    return str(d)\n"
        service_source = b"def format_date(d):\n    return d.isoformat()\n"

        project_symbols: ProjectSymbols = {}
        parser = PythonParser()
        builder = SemanticBuilder()

        # Build index from utils file
        arena_u = parser.parse(utils_source)
        sem_u = builder.build(arena_u, "python")
        for defn in sem_u.definitions:
            project_symbols.setdefault(defn.name, []).append(("utils/dates.py", defn))

        # Build index from service file
        arena_s = parser.parse(service_source)
        sem_s = builder.build(arena_s, "python")
        for defn in sem_s.definitions:
            project_symbols.setdefault(defn.name, []).append(("services/report.py", defn))

        findings = _run_rule(service_source, "services/report.py", project_symbols, tmp_path)
        assert len(findings) >= 1
        assert any("format_date" in f.message for f in findings)  # type: ignore[union-attr]
        assert any("utils/dates.py" in f.message for f in findings)  # type: ignore[union-attr]

    def test_no_flag_same_directory(self, tmp_path: Path) -> None:
        """Two files in same directory with same function → should NOT flag."""
        source_b = b"def helper():\n    pass\n"

        project_symbols: ProjectSymbols = {
            "helper": [
                ("src/a.py", DefinedSymbol(name="helper", kind="function", arena_idx=0)),
                ("src/b.py", DefinedSymbol(name="helper", kind="function", arena_idx=0)),
            ]
        }

        findings = _run_rule(source_b, "src/b.py", project_symbols, tmp_path)
        assert len(findings) == 0

    def test_no_flag_test_file(self, tmp_path: Path) -> None:
        """Function in test file duplicating utils → should NOT flag."""
        source = b"def format_date(d):\n    return str(d)\n"

        project_symbols: ProjectSymbols = {
            "format_date": [
                ("utils/dates.py", DefinedSymbol(name="format_date", kind="function", arena_idx=0)),
                (
                    "tests/test_dates.py",
                    DefinedSymbol(name="format_date", kind="function", arena_idx=0),
                ),
            ]
        }

        findings = _run_rule(source, "tests/test_dates.py", project_symbols, tmp_path)
        assert len(findings) == 0

    def test_no_flag_excluded_names(self, tmp_path: Path) -> None:
        """Common names like 'main', 'run', 'setup' → should NOT flag."""
        source = b"def main():\n    pass\n"

        project_symbols: ProjectSymbols = {
            "main": [
                ("utils/entry.py", DefinedSymbol(name="main", kind="function", arena_idx=0)),
                ("services/app.py", DefinedSymbol(name="main", kind="function", arena_idx=0)),
            ]
        }

        findings = _run_rule(source, "services/app.py", project_symbols, tmp_path)
        assert len(findings) == 0

    def test_no_flag_without_project_symbols(self, tmp_path: Path) -> None:
        """Rule does nothing when project_symbols is None."""
        source = b"def format_date(d):\n    return str(d)\n"
        findings = _run_rule(source, "services/report.py", {}, tmp_path)
        assert len(findings) == 0

    def test_no_flag_other_not_in_utility_dir(self, tmp_path: Path) -> None:
        """Other location not in utility dir → should NOT flag."""
        source = b"def format_date(d):\n    return str(d)\n"

        project_symbols: ProjectSymbols = {
            "format_date": [
                (
                    "models/dates.py",
                    DefinedSymbol(name="format_date", kind="function", arena_idx=0),
                ),
                (
                    "services/report.py",
                    DefinedSymbol(name="format_date", kind="function", arena_idx=0),
                ),
            ]
        }

        findings = _run_rule(source, "services/report.py", project_symbols, tmp_path)
        assert len(findings) == 0


class TestReinventedInternalPickle:
    def test_rule_pickle_roundtrip(self) -> None:
        rule = ReinventedInternalRule()
        data = pickle.dumps(rule)
        restored = pickle.loads(data)  # noqa: S301
        assert restored.id == "reinvented-internal"
