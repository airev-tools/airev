"""Tests for configuration loading from .airev.toml and pyproject.toml."""

from pathlib import Path

from airev_core.config.loader import load_config
from airev_core.config.models import AirevConfig
from airev_core.findings.models import Severity


class TestLoadConfig:
    def test_no_config_files(self, tmp_path: Path) -> None:
        config = load_config(str(tmp_path))
        assert config == AirevConfig()

    def test_airev_toml(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text(
            '[rules]\nhallucinated-api = "off"\nhardcoded-secrets = "error"\n',
            encoding="utf-8",
        )
        config = load_config(str(tmp_path))
        assert not config.rules["hallucinated-api"].enabled
        assert config.rules["hardcoded-secrets"].severity == Severity.ERROR

    def test_pyproject_toml(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.airev]\nexclude = ["vendor/**", "dist/**"]\n',
            encoding="utf-8",
        )
        config = load_config(str(tmp_path))
        assert config.exclude == ("vendor/**", "dist/**")

    def test_airev_toml_takes_precedence(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text('exclude = ["fromairev"]\n', encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.airev]\nexclude = ["frompyproject"]\n', encoding="utf-8"
        )
        config = load_config(str(tmp_path))
        assert config.exclude == ("fromairev",)

    def test_detailed_rule_config(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text(
            '[rules.copy-paste-drift]\nseverity = "warning"\n'
            "similarity_threshold = 0.8\nmin_lines = 10\n",
            encoding="utf-8",
        )
        config = load_config(str(tmp_path))
        rule_cfg = config.rules["copy-paste-drift"]
        assert rule_cfg.severity == Severity.WARNING
        assert rule_cfg.options["similarity_threshold"] == 0.8
        assert rule_cfg.options["min_lines"] == 10

    def test_languages_config(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text(
            '[languages]\nenabled = ["python", "typescript"]\n',
            encoding="utf-8",
        )
        config = load_config(str(tmp_path))
        assert config.languages == frozenset({"python", "typescript"})

    def test_malformed_toml(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text("this is not valid toml {{{\n", encoding="utf-8")
        config = load_config(str(tmp_path))
        assert config == AirevConfig()

    def test_empty_rules_section(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text("[rules]\n", encoding="utf-8")
        config = load_config(str(tmp_path))
        assert config.rules == {}

    def test_empty_exclude(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text("exclude = []\n", encoding="utf-8")
        config = load_config(str(tmp_path))
        assert config.exclude == ()


class TestPickleSafety:
    def test_config_pickleable(self) -> None:
        import pickle

        config = AirevConfig(
            exclude=("vendor/**",),
            rules={
                "phantom-import": __import__(
                    "airev_core.config.models", fromlist=["RuleConfig"]
                ).RuleConfig(enabled=False)
            },
        )
        roundtrip = pickle.loads(pickle.dumps(config))
        assert roundtrip.exclude == config.exclude
