"""Python Tree-sitter parser — lowers CST to UAST arena."""

from __future__ import annotations

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from airev_core.arena.node_types import (
    TYPE_ASSIGNMENT,
    TYPE_CALL,
    TYPE_CLASS_DEF,
    TYPE_DECORATOR,
    TYPE_EXCEPT,
    TYPE_FOR,
    TYPE_FUNCTION_DEF,
    TYPE_IF,
    TYPE_IMPORT,
    TYPE_IMPORT_FROM,
    TYPE_MODULE,
    TYPE_RAISE,
    TYPE_RETURN,
    TYPE_STRING_LITERAL,
    TYPE_TRY,
    TYPE_UNKNOWN,
    TYPE_WHILE,
    TYPE_WITH,
)
from airev_core.arena.uast_arena import UastArena

# Tree-sitter node type string → UAST integer constant
_TS_TO_UAST: dict[str, int] = {
    "module": TYPE_MODULE,
    "import_statement": TYPE_IMPORT,
    "import_from_statement": TYPE_IMPORT_FROM,
    "function_definition": TYPE_FUNCTION_DEF,
    "class_definition": TYPE_CLASS_DEF,
    "call": TYPE_CALL,
    "assignment": TYPE_ASSIGNMENT,
    "decorated_definition": TYPE_DECORATOR,
    "return_statement": TYPE_RETURN,
    "if_statement": TYPE_IF,
    "for_statement": TYPE_FOR,
    "while_statement": TYPE_WHILE,
    "try_statement": TYPE_TRY,
    "except_clause": TYPE_EXCEPT,
    "with_statement": TYPE_WITH,
    "raise_statement": TYPE_RAISE,
    "string": TYPE_STRING_LITERAL,
}


def _node_text(node: Node) -> str:
    """Extract text from a Tree-sitter node, returning empty string if None."""
    text = node.text
    if text is None:
        return ""
    return text.decode("utf-8")


def _extract_name(node: Node, uast_type: int) -> str | None:
    """Extract the name identifier from a Tree-sitter node."""
    if uast_type in (TYPE_FUNCTION_DEF, TYPE_CLASS_DEF):
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return _node_text(name_node)
    elif uast_type == TYPE_IMPORT:
        # For `import numpy as np`, the "name" field is an aliased_import node
        # whose text is "numpy as np".  We need just the module name.
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            if name_node.type == "aliased_import":
                # Extract the dotted_name child (the actual module name)
                for child in name_node.children:
                    if child.type in ("dotted_name", "identifier"):
                        return _node_text(child)
            else:
                return _node_text(name_node)
        for child in node.children:
            if child.type == "aliased_import":
                for sub in child.children:
                    if sub.type in ("dotted_name", "identifier"):
                        return _node_text(sub)
            elif child.type in ("dotted_name", "identifier"):
                return _node_text(child)
    elif uast_type == TYPE_IMPORT_FROM:
        module_node = node.child_by_field_name("module_name")
        if module_node is not None:
            return _node_text(module_node)
        for child in node.children:
            if child.type in ("dotted_name", "identifier"):
                return _node_text(child)
    elif uast_type == TYPE_CALL:
        func_node = node.child_by_field_name("function")
        if func_node is not None:
            return _node_text(func_node)
    return None


class PythonParser:
    """Parses Python source code via Tree-sitter and populates a UastArena."""

    __slots__ = ("_language", "_parser")

    def __init__(self) -> None:
        self._language = Language(tspython.language())
        self._parser = Parser(self._language)

    def parse(self, source: bytes) -> UastArena:
        """Parse Python source code and return a populated UastArena."""
        tree = self._parser.parse(source)
        arena = UastArena()
        self._lower(tree.root_node, arena, parent=-1)
        return arena

    def _lower(self, node: Node, arena: UastArena, parent: int) -> int:
        """Recursively walk CST and populate arena with UAST nodes."""
        uast_type = _TS_TO_UAST.get(node.type, TYPE_UNKNOWN)
        name = _extract_name(node, uast_type)

        idx = arena.allocate(
            node_type=uast_type,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_line=node.start_point[0] + 1,  # Tree-sitter is 0-indexed
            start_col=node.start_point[1],
            parent=parent,
            name=name,
        )

        # Store CST backlink for language-specific access later
        arena.cst_backlinks.append(node)

        for child in node.children:
            self._lower(child, arena, parent=idx)

        return idx
