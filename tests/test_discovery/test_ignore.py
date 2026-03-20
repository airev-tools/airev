"""Tests for .airevignore pattern parsing and matching."""

from pathlib import Path

from airev_core.discovery.ignore import is_ignored, load_ignorefile, parse_ignorefile


class TestParseIgnorefile:
    def test_empty(self) -> None:
        assert parse_ignorefile("") == ()

    def test_comments_and_blanks(self) -> None:
        content = "# comment\n\n# another comment\n"
        assert parse_ignorefile(content) == ()

    def test_simple_glob(self) -> None:
        patterns = parse_ignorefile("*.log\n")
        assert len(patterns) == 1
        assert not patterns[0].negated
        assert not patterns[0].dir_only

    def test_negation(self) -> None:
        patterns = parse_ignorefile("!important.py\n")
        assert len(patterns) == 1
        assert patterns[0].negated

    def test_dir_only(self) -> None:
        patterns = parse_ignorefile("build/\n")
        assert len(patterns) == 1
        assert patterns[0].dir_only

    def test_anchored_pattern(self) -> None:
        patterns = parse_ignorefile("/dist\n")
        assert len(patterns) == 1


class TestIsIgnored:
    def test_glob_match(self) -> None:
        patterns = parse_ignorefile("*.log\n")
        assert is_ignored("app.log", patterns)
        assert is_ignored("src/debug.log", patterns)
        assert not is_ignored("app.py", patterns)

    def test_dir_pattern(self) -> None:
        patterns = parse_ignorefile("vendor/\n")
        assert is_ignored("vendor", patterns, is_dir=True)
        assert not is_ignored("vendor", patterns, is_dir=False)

    def test_double_star(self) -> None:
        patterns = parse_ignorefile("**/test_*.py\n")
        assert is_ignored("tests/test_foo.py", patterns)
        assert is_ignored("src/tests/test_bar.py", patterns)

    def test_anchored_pattern(self) -> None:
        patterns = parse_ignorefile("/dist\n")
        assert is_ignored("dist", patterns)

    def test_negation(self) -> None:
        patterns = parse_ignorefile("*.py\n!important.py\n")
        assert is_ignored("foo.py", patterns)
        assert not is_ignored("important.py", patterns)

    def test_path_normalization(self) -> None:
        patterns = parse_ignorefile("vendor/**\n")
        # Windows-style backslashes should be normalized
        assert is_ignored("vendor\\lib\\foo.py", patterns)

    def test_no_patterns(self) -> None:
        assert not is_ignored("any_file.py", ())

    def test_generated_files(self) -> None:
        patterns = parse_ignorefile("*.min.js\n*.generated.ts\n")
        assert is_ignored("bundle.min.js", patterns)
        assert is_ignored("api.generated.ts", patterns)
        assert not is_ignored("app.js", patterns)


class TestLoadIgnorefile:
    def test_no_file(self, tmp_path: Path) -> None:
        patterns = load_ignorefile(str(tmp_path))
        assert patterns == ()

    def test_with_file(self, tmp_path: Path) -> None:
        ignore = tmp_path / ".airevignore"
        ignore.write_text("*.log\nvendor/\n", encoding="utf-8")
        patterns = load_ignorefile(str(tmp_path))
        assert len(patterns) == 2


class TestPickleSafety:
    def test_patterns_pickleable(self) -> None:
        import pickle

        patterns = parse_ignorefile("*.log\n!keep.log\n")
        roundtrip = pickle.loads(pickle.dumps(patterns))
        assert roundtrip == patterns
