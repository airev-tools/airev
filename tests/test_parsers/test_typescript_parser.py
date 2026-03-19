"""Tests for the JavaScript and TypeScript Tree-sitter parsers."""

from __future__ import annotations

from airev_core.arena.node_types import (
    TYPE_CALL,
    TYPE_FUNCTION_DEF,
    TYPE_IMPORT,
    TYPE_MODULE,
)
from airev_core.parsers.typescript_parser import JavaScriptParser, TypeScriptParser


class TestJavaScriptParser:
    def setup_method(self) -> None:
        self.parser = JavaScriptParser()

    def test_parse_import_default(self) -> None:
        arena = self.parser.parse(b'import fs from "fs"')
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_IMPORT in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_IMPORT:
                assert arena.get_name(i) == "fs"
                break

    def test_parse_import_named(self) -> None:
        arena = self.parser.parse(b'import { readFile } from "fs"')
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_IMPORT in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_IMPORT:
                assert arena.get_name(i) == "fs"
                break

    def test_parse_function_declaration(self) -> None:
        arena = self.parser.parse(b"function hello() {}")
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_FUNCTION_DEF in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_FUNCTION_DEF:
                assert arena.get_name(i) == "hello"
                break

    def test_parse_arrow_function(self) -> None:
        arena = self.parser.parse(b"const fn = () => {}")
        found = False
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_FUNCTION_DEF:
                assert arena.get_name(i) == "fn"
                found = True
                break
        assert found

    def test_parse_call(self) -> None:
        arena = self.parser.parse(b"foo()")
        types = arena.node_types[: arena.count].tolist()
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

    def test_parse_broken_js(self) -> None:
        arena = self.parser.parse(b"function hello( {")
        assert arena.count > 0

    def test_parse_multiline_js(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        source = b"""\
import express from "express"

function greet(name) {
    console.log("Hello, " + name)
}

const add = (a, b) => a + b
"""
        arena = self.parser.parse(source)
        state = {
            "count": arena.count,
            "node_types": arena.node_types[: arena.count].tolist(),
            "names": [arena.get_name(i) for i in range(arena.count)],
        }
        assert state == snapshot


class TestTypeScriptParser:
    def setup_method(self) -> None:
        self.parser = TypeScriptParser()

    def test_parse_import(self) -> None:
        arena = self.parser.parse(b'import { readFile } from "fs"')
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_IMPORT in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_IMPORT:
                assert arena.get_name(i) == "fs"
                break

    def test_parse_function_with_types(self) -> None:
        arena = self.parser.parse(b"function hello(name: string): void {}")
        types = arena.node_types[: arena.count].tolist()
        assert TYPE_FUNCTION_DEF in types
        for i in range(arena.count):
            if arena.node_types[i] == TYPE_FUNCTION_DEF:
                assert arena.get_name(i) == "hello"
                break

    def test_parse_class(self) -> None:
        arena = self.parser.parse(b"class Foo { bar() {} }")
        assert TYPE_MODULE in arena.node_types[: arena.count].tolist()
        assert arena.count > 0

    def test_parse_broken_ts(self) -> None:
        arena = self.parser.parse(b"function foo(: string {")
        assert arena.count > 0
