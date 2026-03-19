"""Tests for the Python Tree-sitter parser."""

from __future__ import annotations

from airev_core.arena.node_types import (
    TYPE_ASSIGNMENT,
    TYPE_CALL,
    TYPE_FUNCTION_DEF,
    TYPE_IMPORT,
    TYPE_IMPORT_FROM,
    TYPE_MODULE,
)
from airev_core.parsers.python_parser import PythonParser


class TestPythonParser:
    def setup_method(self) -> None:
        self.parser = PythonParser()

    def test_parse_import(self) -> None:
        arena = self.parser.parse(b"import os")
        assert arena.count > 0
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_MODULE in types
        assert TYPE_IMPORT in types
        # Find the import node and check its name
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_IMPORT:
                assert arena.get_name(i) == "os"
                break

    def test_parse_import_from(self) -> None:
        arena = self.parser.parse(b"from pathlib import Path")
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_IMPORT_FROM in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_IMPORT_FROM:
                assert arena.get_name(i) == "pathlib"
                break

    def test_parse_function_def(self) -> None:
        arena = self.parser.parse(b"def hello(): pass")
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_FUNCTION_DEF in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_FUNCTION_DEF:
                assert arena.get_name(i) == "hello"
                break

    def test_parse_call(self) -> None:
        arena = self.parser.parse(b"x = foo()")
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_ASSIGNMENT in types
        assert TYPE_CALL in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_CALL:
                assert arena.get_name(i) == "foo"
                break

    def test_parse_method_call(self) -> None:
        arena = self.parser.parse(b"obj.method()")
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_CALL in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_CALL:
                name = arena.get_name(i)
                assert name is not None
                assert "method" in name
                break

    def test_parse_multiline_file(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        source = b"""\
import os
from pathlib import Path

def greet(name):
    print(f"Hello, {name}")

class Foo:
    def bar(self):
        return self.baz()
"""
        arena = self.parser.parse(source)
        state = {
            "count": arena.count,
            "node_types": arena.node_types[: arena.count].tolist(),
            "names": [arena.get_name(i) for i in range(arena.count)],
        }
        assert state == snapshot

    def test_parse_broken_syntax(self) -> None:
        # Tree-sitter should handle this without crashing
        arena = self.parser.parse(b"def foo(\n  pass")
        assert arena.count > 0

    def test_parse_empty_source(self) -> None:
        arena = self.parser.parse(b"")
        assert arena.count >= 1  # At least the module node
