"""Tests for inline suppression via # airev: ignore directives."""

from airev_core.suppression import (
    build_suppression_map,
    is_finding_suppressed,
    parse_ignore_directive,
)


class TestParseIgnoreDirective:
    def test_no_directive(self) -> None:
        has, ids = parse_ignore_directive("# This is a normal comment")
        assert not has

    def test_bare_ignore(self) -> None:
        has, ids = parse_ignore_directive("# airev: ignore")
        assert has
        assert ids == frozenset()

    def test_single_rule(self) -> None:
        has, ids = parse_ignore_directive("# airev: ignore[phantom-import]")
        assert has
        assert ids == frozenset({"phantom-import"})

    def test_multiple_rules(self) -> None:
        has, ids = parse_ignore_directive("# airev: ignore[phantom-import, hardcoded-secrets]")
        assert has
        assert ids == frozenset({"phantom-import", "hardcoded-secrets"})

    def test_js_style_comment(self) -> None:
        has, ids = parse_ignore_directive("// airev: ignore[hallucinated-api]")
        assert has
        assert ids == frozenset({"hallucinated-api"})

    def test_with_surrounding_text(self) -> None:
        has, ids = parse_ignore_directive("x = 42  # airev: ignore[hardcoded-secrets] safe value")
        assert has
        assert ids == frozenset({"hardcoded-secrets"})


class TestBuildSuppressionMap:
    def test_python_comment(self) -> None:
        source = b'api_key = "test"  # airev: ignore[hardcoded-secrets]\n'
        sup = build_suppression_map(source, "python")
        assert 1 in sup
        assert sup[1] == frozenset({"hardcoded-secrets"})

    def test_js_comment(self) -> None:
        source = b'const key = "test"; // airev: ignore[hardcoded-secrets]\n'
        sup = build_suppression_map(source, "javascript")
        assert 1 in sup

    def test_directive_inside_string_ignored_python(self) -> None:
        source = b'msg = "# airev: ignore[phantom-import]"\n'
        sup = build_suppression_map(source, "python")
        assert sup == {}

    def test_directive_inside_string_ignored_js(self) -> None:
        source = b'const msg = "// airev: ignore[phantom-import]";\n'
        sup = build_suppression_map(source, "javascript")
        assert sup == {}

    def test_multiple_lines(self) -> None:
        source = (
            b"import foo  # airev: ignore[phantom-import]\n"
            b"import bar\n"
            b'x = "secret"  # airev: ignore\n'
        )
        sup = build_suppression_map(source, "python")
        assert 1 in sup
        assert 2 not in sup
        assert 3 in sup
        assert sup[3] == frozenset()  # bare ignore = all rules

    def test_empty_source(self) -> None:
        sup = build_suppression_map(b"", "python")
        assert sup == {}

    def test_invalid_utf8(self) -> None:
        sup = build_suppression_map(b"\x80\x81\x82", "python")
        assert sup == {}  # graceful handling


class TestIsFindingSuppressed:
    def test_suppressed_specific_rule(self) -> None:
        sup = {1: frozenset({"phantom-import"})}
        assert is_finding_suppressed(sup, "phantom-import", 1)

    def test_not_suppressed_different_rule(self) -> None:
        sup = {1: frozenset({"phantom-import"})}
        assert not is_finding_suppressed(sup, "hardcoded-secrets", 1)

    def test_suppressed_all_rules(self) -> None:
        sup = {1: frozenset()}
        assert is_finding_suppressed(sup, "any-rule", 1)

    def test_not_suppressed_different_line(self) -> None:
        sup = {1: frozenset({"phantom-import"})}
        assert not is_finding_suppressed(sup, "phantom-import", 2)

    def test_empty_map(self) -> None:
        assert not is_finding_suppressed({}, "phantom-import", 1)


class TestDirectiveInTemplateString:
    def test_js_template_literal(self) -> None:
        source = b"const msg = `// airev: ignore[phantom-import]`;\n"
        sup = build_suppression_map(source, "javascript")
        assert sup == {}

    def test_js_real_comment_after_template(self) -> None:
        source = b"const x = `hello`; // airev: ignore[phantom-import]\n"
        sup = build_suppression_map(source, "javascript")
        assert 1 in sup


class TestPickleSafety:
    def test_suppression_map_pickleable(self) -> None:
        import pickle

        sup = build_suppression_map(b"x = 1  # airev: ignore[phantom-import]\n", "python")
        roundtrip = pickle.loads(pickle.dumps(sup))
        assert roundtrip == sup
