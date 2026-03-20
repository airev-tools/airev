"""Tests for evidence-based confidence calibration."""

from pathlib import Path

from airev_core.findings.models import Confidence
from airev_core.rules.evidence import (
    EvidenceFlags,
    calibrate_confidence,
    gather_evidence,
)
from airev_core.semantics.context import LintContext
from airev_core.semantics.resolver import ImportResolver
from airev_core.workspace.models import WorkspaceFacts


def _make_facts(**kwargs: object) -> WorkspaceFacts:
    defaults = {
        "project_root": "/tmp/test",
        "languages": frozenset({"python"}),
        "manifest_paths": ("pyproject.toml",),
        "first_party_prefixes": frozenset({"myapp"}),
        "third_party_dependencies": frozenset({"requests", "click"}),
        "python_module_roots": ("myapp",),
        "package_names": frozenset({"myapp"}),
        "ts_path_aliases": (),
        "has_lockfile": False,
    }
    defaults.update(kwargs)
    return WorkspaceFacts(**defaults)  # type: ignore[arg-type]


class TestCalibrateConfidence:
    def test_first_party_lowers_confidence(self) -> None:
        evidence = EvidenceFlags(import_matches_first_party_prefix=True)
        result = calibrate_confidence(evidence, Confidence.HIGH)
        assert result == Confidence.LOW

    def test_declared_but_not_installed_is_medium(self) -> None:
        evidence = EvidenceFlags(
            dependency_manifest_present=True,
            import_matches_declared_dependency=True,
            dependencies_installed=False,
        )
        result = calibrate_confidence(evidence, Confidence.HIGH)
        assert result == Confidence.MEDIUM

    def test_tsconfig_alias_lowers_confidence(self) -> None:
        evidence = EvidenceFlags(import_matches_tsconfig_alias=True)
        result = calibrate_confidence(evidence, Confidence.HIGH)
        assert result == Confidence.LOW

    def test_generated_file_lowers_confidence(self) -> None:
        evidence = EvidenceFlags(file_is_generated=True)
        result = calibrate_confidence(evidence, Confidence.HIGH)
        assert result == Confidence.LOW

    def test_no_manifest_no_deps_is_low(self) -> None:
        evidence = EvidenceFlags(
            dependency_manifest_present=False,
            dependencies_installed=False,
        )
        result = calibrate_confidence(evidence, Confidence.HIGH)
        assert result == Confidence.LOW

    def test_fully_resolved_stays_high(self) -> None:
        evidence = EvidenceFlags(
            dependency_manifest_present=True,
            dependencies_installed=True,
        )
        result = calibrate_confidence(evidence, Confidence.HIGH)
        assert result == Confidence.HIGH


class TestGatherEvidence:
    def test_first_party_detected(self, tmp_path: Path) -> None:
        facts = _make_facts(first_party_prefixes=frozenset({"myapp"}))
        resolver = ImportResolver(str(tmp_path), "python")
        from airev_core.arena.uast_arena import UastArena
        from airev_core.semantics.symbols import SemanticModel

        arena = UastArena(capacity=1)
        semantic = SemanticModel(
            imports=(),
            definitions=(),
            calls=(),
            import_table={},
            definition_table={},
        )
        ctx = LintContext(
            arena=arena,
            semantic=semantic,
            file_path="test.py",
            language="python",
            source=b"",
            resolver=resolver,
            workspace_facts=facts,
        )
        evidence = gather_evidence("myapp.utils", ctx)
        assert evidence.import_matches_first_party_prefix

    def test_declared_dependency_detected(self, tmp_path: Path) -> None:
        facts = _make_facts(third_party_dependencies=frozenset({"requests"}))
        resolver = ImportResolver(str(tmp_path), "python")
        from airev_core.arena.uast_arena import UastArena
        from airev_core.semantics.symbols import SemanticModel

        arena = UastArena(capacity=1)
        semantic = SemanticModel(
            imports=(),
            definitions=(),
            calls=(),
            import_table={},
            definition_table={},
        )
        ctx = LintContext(
            arena=arena,
            semantic=semantic,
            file_path="test.py",
            language="python",
            source=b"",
            resolver=resolver,
            workspace_facts=facts,
        )
        evidence = gather_evidence("requests", ctx)
        assert evidence.import_matches_declared_dependency

    def test_ts_alias_detected(self, tmp_path: Path) -> None:
        facts = _make_facts(
            ts_path_aliases=(("@utils/*", "src/utils/*"),),
            languages=frozenset({"typescript"}),
        )
        resolver = ImportResolver(str(tmp_path), "typescript")
        from airev_core.arena.uast_arena import UastArena
        from airev_core.semantics.symbols import SemanticModel

        arena = UastArena(capacity=1)
        semantic = SemanticModel(
            imports=(),
            definitions=(),
            calls=(),
            import_table={},
            definition_table={},
        )
        ctx = LintContext(
            arena=arena,
            semantic=semantic,
            file_path="test.ts",
            language="typescript",
            source=b"",
            resolver=resolver,
            workspace_facts=facts,
        )
        evidence = gather_evidence("@utils/helpers", ctx)
        assert evidence.import_matches_tsconfig_alias

    def test_no_facts_returns_empty_evidence(self, tmp_path: Path) -> None:
        resolver = ImportResolver(str(tmp_path), "python")
        from airev_core.arena.uast_arena import UastArena
        from airev_core.semantics.symbols import SemanticModel

        arena = UastArena(capacity=1)
        semantic = SemanticModel(
            imports=(),
            definitions=(),
            calls=(),
            import_table={},
            definition_table={},
        )
        ctx = LintContext(
            arena=arena,
            semantic=semantic,
            file_path="test.py",
            language="python",
            source=b"",
            resolver=resolver,
        )
        evidence = gather_evidence("something", ctx)
        assert not evidence.dependency_manifest_present


class TestPickleSafety:
    def test_evidence_pickleable(self) -> None:
        import pickle

        evidence = EvidenceFlags(
            dependency_manifest_present=True,
            import_matches_first_party_prefix=True,
        )
        rt = pickle.loads(pickle.dumps(evidence))
        assert rt.dependency_manifest_present
