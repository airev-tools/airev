"""Tests for ParserRegistry."""

from __future__ import annotations

from airev_core.parsers import ParserRegistry
from airev_core.parsers.python_parser import PythonParser
from airev_core.parsers.typescript_parser import JavaScriptParser, TypeScriptParser


class TestParserRegistry:
    def setup_method(self) -> None:
        self.registry = ParserRegistry()

    def test_python_extension(self) -> None:
        parser = self.registry.get_parser("main.py")
        assert isinstance(parser, PythonParser)

    def test_js_extension(self) -> None:
        parser = self.registry.get_parser("app.js")
        assert isinstance(parser, JavaScriptParser)

    def test_jsx_extension(self) -> None:
        parser = self.registry.get_parser("component.jsx")
        assert isinstance(parser, JavaScriptParser)

    def test_ts_extension(self) -> None:
        parser = self.registry.get_parser("index.ts")
        assert isinstance(parser, TypeScriptParser)

    def test_tsx_extension(self) -> None:
        parser = self.registry.get_parser("component.tsx")
        assert isinstance(parser, TypeScriptParser)

    def test_unsupported_extension(self) -> None:
        assert self.registry.get_parser("main.go") is None
        assert self.registry.get_parser("lib.rs") is None
        assert self.registry.get_parser("readme.txt") is None

    def test_get_language(self) -> None:
        assert self.registry.get_language("foo.py") == "python"
        assert self.registry.get_language("foo.js") == "javascript"
        assert self.registry.get_language("foo.ts") == "typescript"
        assert self.registry.get_language("foo.go") is None

    def test_parser_caching(self) -> None:
        p1 = self.registry.get_parser("a.py")
        p2 = self.registry.get_parser("b.py")
        assert p1 is p2

    def test_supported_extensions(self) -> None:
        exts = self.registry.supported_extensions
        assert ".py" in exts
        assert ".js" in exts
        assert ".ts" in exts
        assert ".tsx" in exts
        assert ".jsx" in exts
