"""Edge case tests for configuration loading."""

from pathlib import Path

from airev_core.config.loader import load_config
from airev_core.config.models import AirevConfig


class TestConfigEdges:
    def test_malformed_toml_partial_recovery(self, tmp_path: Path) -> None:
        """Malformed TOML returns default config without crash."""
        (tmp_path / ".airev.toml").write_text("{{{invalid", encoding="utf-8")
        config = load_config(str(tmp_path))
        assert config == AirevConfig()

    def test_unknown_severity_value(self, tmp_path: Path) -> None:
        """Unknown severity value is ignored, rule stays enabled."""
        (tmp_path / ".airev.toml").write_text(
            '[rules]\nphantom-import = "extreme"\n', encoding="utf-8"
        )
        config = load_config(str(tmp_path))
        # "extreme" is not valid — rule entry may exist but with no severity override
        assert "phantom-import" not in config.rules or config.rules["phantom-import"].enabled

    def test_precedence_airev_over_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text('exclude = ["a"]\n', encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.airev]\nexclude = ["b"]\n', encoding="utf-8"
        )
        config = load_config(str(tmp_path))
        assert config.exclude == ("a",)

    def test_empty_arrays(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text("exclude = []\n[rules]\n", encoding="utf-8")
        config = load_config(str(tmp_path))
        assert config.exclude == ()
        assert config.rules == {}

    def test_rule_config_for_missing_rule(self, tmp_path: Path) -> None:
        """Config for a rule that doesn't exist should not crash."""
        (tmp_path / ".airev.toml").write_text(
            '[rules]\nnonexistent-rule = "off"\n', encoding="utf-8"
        )
        config = load_config(str(tmp_path))
        assert not config.rules["nonexistent-rule"].enabled

    def test_empty_toml_file(self, tmp_path: Path) -> None:
        (tmp_path / ".airev.toml").write_text("", encoding="utf-8")
        config = load_config(str(tmp_path))
        assert config == AirevConfig()
