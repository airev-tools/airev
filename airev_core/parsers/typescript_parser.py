"""JavaScript and TypeScript Tree-sitter parsers — lower CST to UAST arena."""

from __future__ import annotations

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from airev_core.arena.node_types import (
    TYPE_ASSIGNMENT,
    TYPE_CALL,
    TYPE_CLASS_DEF,
    TYPE_EXCEPT,
    TYPE_FOR,
    TYPE_FUNCTION_DEF,
    TYPE_IF,
    TYPE_IMPORT,
    TYPE_MODULE,
    TYPE_RETURN,
    TYPE_STRING_LITERAL,
    TYPE_TRY,
    TYPE_UNKNOWN,
    TYPE_WHILE,
    TYPE_WITH,
)
from airev_core.arena.uast_arena import UastArena

# Tree-sitter JS/TS node type string → UAST integer constant
_TS_TO_UAST: dict[str, int] = {
    "program": TYPE_MODULE,
    "import_statement": TYPE_IMPORT,
    "function_declaration": TYPE_FUNCTION_DEF,
    "arrow_function": TYPE_FUNCTION_DEF,
    "generator_function_declaration": TYPE_FUNCTION_DEF,
    "class_declaration": TYPE_CLASS_DEF,
    "call_expression": TYPE_CALL,
    "new_expression": TYPE_CALL,
    "variable_declaration": TYPE_ASSIGNMENT,
    "lexical_declaration": TYPE_ASSIGNMENT,
    "assignment_expression": TYPE_ASSIGNMENT,
    "return_statement": TYPE_RETURN,
    "if_statement": TYPE_IF,
    "for_statement": TYPE_FOR,
    "for_in_statement": TYPE_FOR,
    "while_statement": TYPE_WHILE,
    "try_statement": TYPE_TRY,
    "catch_clause": TYPE_EXCEPT,
    "with_statement": TYPE_WITH,
    "string": TYPE_STRING_LITERAL,
    "template_string": TYPE_STRING_LITERAL,
}


def _node_text(node: Node) -> str:
    """Extract text from a Tree-sitter node, returning empty string if None."""
    text = node.text
    if text is None:
        return ""
    return text.decode("utf-8")


def _extract_name(node: Node, uast_type: int) -> str | None:
    """Extract the name identifier from a JS/TS Tree-sitter node."""
    if uast_type == TYPE_FUNCTION_DEF:
        # function_declaration has a "name" field
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return _node_text(name_node)
        # arrow_function: check if parent is variable_declarator
        if (
            node.type == "arrow_function"
            and node.parent is not None
            and node.parent.type == "variable_declarator"
        ):
            var_name = node.parent.child_by_field_name("name")
            if var_name is not None:
                return _node_text(var_name)
    elif uast_type == TYPE_CLASS_DEF:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return _node_text(name_node)
    elif uast_type == TYPE_IMPORT:
        # import ... from "source"
        source_node = node.child_by_field_name("source")
        if source_node is not None:
            raw = _node_text(source_node)
            return raw.strip("'\"")
    elif uast_type == TYPE_CALL:
        func_node = node.child_by_field_name("function")
        if func_node is not None:
            return _node_text(func_node)
    return None


def _lower(node: Node, arena: UastArena, parent: int) -> int:
    """Recursively walk CST and populate arena with UAST nodes."""
    uast_type = _TS_TO_UAST.get(node.type, TYPE_UNKNOWN)
    name = _extract_name(node, uast_type)

    idx = arena.allocate(
        node_type=uast_type,
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        start_line=node.start_point[0] + 1,
        start_col=node.start_point[1],
        parent=parent,
        name=name,
    )

    arena.cst_backlinks.append(node)

    for child in node.children:
        _lower(child, arena, parent=idx)

    return idx


class JavaScriptParser:
    """Parses JavaScript source code (.js, .jsx) via Tree-sitter."""

    __slots__ = ("_language", "_parser")

    def __init__(self) -> None:
        self._language = Language(tsjs.language())
        self._parser = Parser(self._language)

    def parse(self, source: bytes) -> UastArena:
        """Parse JavaScript source code and return a populated UastArena."""
        tree = self._parser.parse(source)
        arena = UastArena()
        _lower(tree.root_node, arena, parent=-1)
        return arena


class TypeScriptParser:
    """Parses TypeScript source code (.ts, .tsx) via Tree-sitter."""

    __slots__ = ("_language", "_parser")

    def __init__(self) -> None:
        self._language = Language(tsts.language_typescript())
        self._parser = Parser(self._language)

    def parse(self, source: bytes) -> UastArena:
        """Parse TypeScript source code and return a populated UastArena."""
        tree = self._parser.parse(source)
        arena = UastArena()
        _lower(tree.root_node, arena, parent=-1)
        return arena
