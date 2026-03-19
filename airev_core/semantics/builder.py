"""SemanticBuilder — extracts semantic information from a populated UastArena."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from airev_core.arena.node_types import (
    TYPE_ASSIGNMENT,
    TYPE_CALL,
    TYPE_CLASS_DEF,
    TYPE_FUNCTION_DEF,
    TYPE_IMPORT,
    TYPE_IMPORT_FROM,
)
from airev_core.semantics.symbols import (
    CallSite,
    DefinedSymbol,
    ImportedSymbol,
    SemanticModel,
)

if TYPE_CHECKING:
    from airev_core.arena.uast_arena import UastArena


def _node_text(node: Any) -> str:
    """Extract text from a Tree-sitter CST node."""
    text = node.text
    if text is None:
        return ""
    result: str = text.decode("utf-8")
    return result


class SemanticBuilder:
    """Extracts semantic information from a populated UastArena.

    Call build() once — it walks the arena and returns a frozen SemanticModel.
    """

    def build(self, arena: UastArena, language: str) -> SemanticModel:
        """Single pre-pass over the arena. Extracts imports, definitions, and calls."""
        imports: list[ImportedSymbol] = []
        definitions: list[DefinedSymbol] = []
        calls: list[CallSite] = []

        for idx in range(arena.count):
            node_type = int(arena.node_types[idx])

            if node_type == TYPE_IMPORT:
                if language == "python":
                    imports.extend(self._extract_python_import(arena, idx))
                else:
                    imports.extend(self._extract_js_import(arena, idx))
            elif node_type == TYPE_IMPORT_FROM:
                imports.extend(self._extract_python_from_import(arena, idx))
            elif node_type == TYPE_FUNCTION_DEF:
                defn = self._extract_definition(arena, idx, "function")
                if defn is not None:
                    definitions.append(defn)
            elif node_type == TYPE_CLASS_DEF:
                defn = self._extract_definition(arena, idx, "class")
                if defn is not None:
                    definitions.append(defn)
            elif node_type == TYPE_ASSIGNMENT:
                defn = self._extract_assignment(arena, idx)
                if defn is not None:
                    definitions.append(defn)
            elif node_type == TYPE_CALL:
                call = self._extract_call(arena, idx)
                if call is not None:
                    calls.append(call)

        import_table = {imp.local_name: imp for imp in imports}
        definition_table = {defn.name: defn for defn in definitions}

        return SemanticModel(
            imports=tuple(imports),
            definitions=tuple(definitions),
            calls=tuple(calls),
            import_table=import_table,
            definition_table=definition_table,
        )

    def _extract_python_import(self, arena: UastArena, idx: int) -> list[ImportedSymbol]:
        """Handle `import os` and `import numpy as np`."""
        results: list[ImportedSymbol] = []
        cst = self._get_cst(arena, idx)
        if cst is None:
            return results

        for child in cst.children:
            if child.type == "dotted_name":
                module = _node_text(child)
                results.append(
                    ImportedSymbol(
                        module=module,
                        name=None,
                        alias=None,
                        local_name=module,
                        arena_idx=idx,
                        is_from_import=False,
                    )
                )
            elif child.type == "aliased_import":
                module_node = None
                alias_node = None
                for gc in child.children:
                    if gc.type in ("dotted_name", "identifier") and module_node is None:
                        module_node = gc
                    elif gc.type == "identifier" and module_node is not None:
                        alias_node = gc
                if module_node is not None:
                    module = _node_text(module_node)
                    alias = _node_text(alias_node) if alias_node is not None else None
                    local_name = alias if alias else module
                    results.append(
                        ImportedSymbol(
                            module=module,
                            name=None,
                            alias=alias,
                            local_name=local_name,
                            arena_idx=idx,
                            is_from_import=False,
                        )
                    )

        return results

    def _extract_python_from_import(self, arena: UastArena, idx: int) -> list[ImportedSymbol]:
        """Handle `from os.path import join, exists` and `from x import y as z`."""
        results: list[ImportedSymbol] = []
        cst = self._get_cst(arena, idx)
        if cst is None:
            return results

        # Find the module name (first dotted_name/identifier after 'from')
        module_name = arena.get_name(idx) or ""

        # Find imported names
        found_import_keyword = False
        for child in cst.children:
            if child.type == "import":
                found_import_keyword = True
                continue
            if not found_import_keyword:
                continue

            if child.type in ("dotted_name", "identifier"):
                name = _node_text(child)
                results.append(
                    ImportedSymbol(
                        module=module_name,
                        name=name,
                        alias=None,
                        local_name=name,
                        arena_idx=idx,
                        is_from_import=True,
                    )
                )
            elif child.type == "aliased_import":
                name_node = None
                alias_node = None
                for gc in child.children:
                    if gc.type in ("dotted_name", "identifier") and name_node is None:
                        name_node = gc
                    elif gc.type == "identifier" and name_node is not None:
                        alias_node = gc
                if name_node is not None:
                    name = _node_text(name_node)
                    alias = _node_text(alias_node) if alias_node is not None else None
                    local_name = alias if alias else name
                    results.append(
                        ImportedSymbol(
                            module=module_name,
                            name=name,
                            alias=alias,
                            local_name=local_name,
                            arena_idx=idx,
                            is_from_import=True,
                        )
                    )

        return results

    def _extract_js_import(self, arena: UastArena, idx: int) -> list[ImportedSymbol]:
        """Handle JS/TS imports: default, named, and namespace."""
        results: list[ImportedSymbol] = []
        cst = self._get_cst(arena, idx)
        if cst is None:
            return results

        module = arena.get_name(idx) or ""

        # Find import_clause
        for child in cst.children:
            if child.type != "import_clause":
                continue
            for clause_child in child.children:
                if clause_child.type == "identifier":
                    # Default import: import fs from "fs"
                    local = _node_text(clause_child)
                    results.append(
                        ImportedSymbol(
                            module=module,
                            name="default",
                            alias=None,
                            local_name=local,
                            arena_idx=idx,
                            is_from_import=False,
                        )
                    )
                elif clause_child.type == "named_imports":
                    # Named import: import { readFile } from "fs"
                    for spec in clause_child.children:
                        if spec.type == "import_specifier":
                            name_node = spec.child_by_field_name("name")
                            alias_node = spec.child_by_field_name("alias")
                            if name_node is not None:
                                name = _node_text(name_node)
                                alias = _node_text(alias_node) if alias_node else None
                                local = alias if alias else name
                                results.append(
                                    ImportedSymbol(
                                        module=module,
                                        name=name,
                                        alias=alias,
                                        local_name=local,
                                        arena_idx=idx,
                                        is_from_import=True,
                                    )
                                )
                elif clause_child.type == "namespace_import":
                    # Namespace import: import * as path from "path"
                    for ns_child in clause_child.children:
                        if ns_child.type == "identifier":
                            local = _node_text(ns_child)
                            results.append(
                                ImportedSymbol(
                                    module=module,
                                    name="*",
                                    alias=local,
                                    local_name=local,
                                    arena_idx=idx,
                                    is_from_import=False,
                                )
                            )
                            break

        return results

    def _extract_definition(self, arena: UastArena, idx: int, kind: str) -> DefinedSymbol | None:
        """Extract a function or class definition."""
        name = arena.get_name(idx)
        if name is None:
            return None
        return DefinedSymbol(name=name, kind=kind, arena_idx=idx)

    def _extract_assignment(self, arena: UastArena, idx: int) -> DefinedSymbol | None:
        """Extract a variable assignment definition from the CST."""
        cst = self._get_cst(arena, idx)
        if cst is None:
            return None

        # Python: assignment has 'left' field
        left = cst.child_by_field_name("left")
        if left is not None and left.type == "identifier":
            return DefinedSymbol(name=_node_text(left), kind="variable", arena_idx=idx)

        # JS/TS: lexical_declaration / variable_declaration → variable_declarator → name
        for child in cst.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                if name_node is not None and name_node.type == "identifier":
                    return DefinedSymbol(name=_node_text(name_node), kind="variable", arena_idx=idx)

        return None

    def _extract_call(self, arena: UastArena, idx: int) -> CallSite | None:
        """Extract a call site with receiver info."""
        full_name = arena.get_name(idx)
        if full_name is None:
            return None

        # Split "obj.method" into receiver="obj", name="method"
        dot_pos = full_name.rfind(".")
        if dot_pos != -1:
            receiver = full_name[:dot_pos]
            name = full_name[dot_pos + 1 :]
        else:
            receiver = None
            name = full_name

        return CallSite(
            name=name,
            receiver=receiver,
            full_name=full_name,
            arena_idx=idx,
        )

    def _get_cst(self, arena: UastArena, idx: int) -> Any | None:
        """Get the CST backlink for an arena node, if available."""
        if idx < len(arena.cst_backlinks):
            return arena.cst_backlinks[idx]
        return None
