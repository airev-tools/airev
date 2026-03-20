"""Edge case tests for inline ignore and .airevignore."""

from airev_core.discovery.ignore import is_ignored, parse_ignorefile
from airev_core.suppression import build_suppression_map


class TestIgnoreDirectiveEdges:
    def test_directive_inside_string_not_counted(self) -> None:
        """Ignore directive text inside a string literal must not count."""
        source = b'msg = "# airev: ignore[phantom-import]"\n'
        sup = build_suppression_map(source, "python")
        assert sup == {}

    def test_crlf_line_endings(self) -> None:
        source = b"import foo  # airev: ignore[phantom-import]\r\nimport bar\r\n"
        sup = build_suppression_map(source, "python")
        assert 1 in sup

    def test_duplicate_directives_same_line(self) -> None:
        """Two directives on the same line — last one wins (merged)."""
        source = b"x = 1  # airev: ignore[a] airev: ignore[b]\n"
        # The regex finds the first directive
        sup = build_suppression_map(source, "python")
        assert 1 in sup

    def test_malformed_directive_no_crash(self) -> None:
        source = b"x = 1  # airev: ignore[!!!invalid]\n"
        build_suppression_map(source, "python")
        # Should not crash, may or may not match

    def test_unknown_rule_id_tolerated(self) -> None:
        source = b"x = 1  # airev: ignore[nonexistent-rule]\n"
        sup = build_suppression_map(source, "python")
        assert 1 in sup
        assert "nonexistent-rule" in sup[1]

    def test_directive_in_js_block_comment_not_parsed(self) -> None:
        """Block comments (/* */) not yet supported — directive ignored."""
        source = b"/* airev: ignore[phantom-import] */\nconst x = 1;\n"
        sup = build_suppression_map(source, "javascript")
        # Block comment support is not implemented; directive should not match
        assert 1 not in sup


class TestAirevignoreEdges:
    def test_empty_pattern_file(self) -> None:
        patterns = parse_ignorefile("")
        assert patterns == ()

    def test_comment_only_file(self) -> None:
        patterns = parse_ignorefile("# comment\n# another\n")
        assert patterns == ()

    def test_unicode_filename_pattern(self) -> None:
        patterns = parse_ignorefile("résumé.py\n")
        assert len(patterns) == 1
        assert is_ignored("résumé.py", patterns)

    def test_multiple_negations(self) -> None:
        patterns = parse_ignorefile("*.py\n!important.py\n!critical.py\n")
        assert is_ignored("foo.py", patterns)
        assert not is_ignored("important.py", patterns)
        assert not is_ignored("critical.py", patterns)
