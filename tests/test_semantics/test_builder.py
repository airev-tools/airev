"""Tests for SemanticBuilder."""

from __future__ import annotations

import pickle

from airev_core.parsers.python_parser import PythonParser
from airev_core.parsers.typescript_parser import JavaScriptParser
from airev_core.semantics.builder import SemanticBuilder


class TestSemanticBuilderPython:
    def setup_method(self) -> None:
        self.parser = PythonParser()
        self.builder = SemanticBuilder()

    def _build(self, source: bytes) -> object:
        arena = self.parser.parse(source)
        return self.builder.build(arena, "python")

    def test_simple_imports(self) -> None:
        model = self._build(b"import os\nimport numpy as np")
        assert len(model.imports) == 2  # type: ignore[union-attr]
        imp_os = model.imports[0]  # type: ignore[union-attr]
        assert imp_os.module == "os"
        assert imp_os.local_name == "os"
        assert imp_os.alias is None
        imp_np = model.imports[1]  # type: ignore[union-attr]
        assert imp_np.module == "numpy"
        assert imp_np.alias == "np"
        assert imp_np.local_name == "np"

    def test_from_imports(self) -> None:
        model = self._build(b"from os.path import join, exists")
        assert len(model.imports) == 2  # type: ignore[union-attr]
        assert model.imports[0].module == "os.path"  # type: ignore[union-attr]
        assert model.imports[0].name == "join"  # type: ignore[union-attr]
        assert model.imports[0].local_name == "join"  # type: ignore[union-attr]
        assert model.imports[1].name == "exists"  # type: ignore[union-attr]

    def test_definitions(self) -> None:
        model = self._build(b"def hello(): pass\nclass Foo: pass")
        assert len(model.definitions) == 2  # type: ignore[union-attr]
        assert model.definitions[0].name == "hello"  # type: ignore[union-attr]
        assert model.definitions[0].kind == "function"  # type: ignore[union-attr]
        assert model.definitions[1].name == "Foo"  # type: ignore[union-attr]
        assert model.definitions[1].kind == "class"  # type: ignore[union-attr]

    def test_call_with_receiver(self) -> None:
        model = self._build(b"np.array([1,2,3])")
        calls = [c for c in model.calls if c.receiver is not None]  # type: ignore[union-attr]
        assert len(calls) >= 1
        assert calls[0].receiver == "np"
        assert calls[0].name == "array"
        assert calls[0].full_name == "np.array"

    def test_import_table_lookup(self) -> None:
        model = self._build(b"import numpy as np\nimport os")
        assert "np" in model.import_table  # type: ignore[union-attr]
        assert "os" in model.import_table  # type: ignore[union-attr]
        assert model.import_table["np"].module == "numpy"  # type: ignore[union-attr]

    def test_snapshot_python(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        source = b"""\
import os
import numpy as np
from pathlib import Path
from collections import defaultdict, OrderedDict

def greet(name):
    print(f"Hello, {name}")

def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y

result = np.array([1, 2, 3])
mean = np.mean(result)
files = os.listdir(".")
p = Path(".")
"""
        arena = self.parser.parse(source)
        model = self.builder.build(arena, "python")
        state = {
            "imports": [
                {"module": i.module, "name": i.name, "local_name": i.local_name}
                for i in model.imports
            ],
            "definitions": [{"name": d.name, "kind": d.kind} for d in model.definitions],
            "calls": [
                {"name": c.name, "receiver": c.receiver, "full_name": c.full_name}
                for c in model.calls
            ],
        }
        assert state == snapshot

    def test_pickle_roundtrip(self) -> None:
        arena = self.parser.parse(b"import os\ndef hello(): pass\nos.listdir('.')")
        model = self.builder.build(arena, "python")
        restored = pickle.loads(pickle.dumps(model))
        assert len(restored.imports) == len(model.imports)
        assert len(restored.definitions) == len(model.definitions)
        assert len(restored.calls) == len(model.calls)
        assert restored.import_table.keys() == model.import_table.keys()


class TestSemanticBuilderJavaScript:
    def setup_method(self) -> None:
        self.parser = JavaScriptParser()
        self.builder = SemanticBuilder()

    def test_default_import(self) -> None:
        arena = self.parser.parse(b'import fs from "fs"')
        model = self.builder.build(arena, "javascript")
        assert len(model.imports) == 1
        assert model.imports[0].module == "fs"
        assert model.imports[0].local_name == "fs"
        assert model.imports[0].name == "default"

    def test_named_import(self) -> None:
        arena = self.parser.parse(b'import { readFile } from "fs"')
        model = self.builder.build(arena, "javascript")
        assert len(model.imports) == 1
        assert model.imports[0].module == "fs"
        assert model.imports[0].name == "readFile"
        assert model.imports[0].local_name == "readFile"

    def test_namespace_import(self) -> None:
        arena = self.parser.parse(b'import * as path from "path"')
        model = self.builder.build(arena, "javascript")
        assert len(model.imports) == 1
        assert model.imports[0].module == "path"
        assert model.imports[0].local_name == "path"
        assert model.imports[0].name == "*"

    def test_snapshot_js(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        source = b"""\
import express from "express"
import { readFile, writeFile } from "fs"
import * as path from "path"

function greet(name) {
    console.log("Hello, " + name)
}

const result = express()
const fullPath = path.join("a", "b")
"""
        arena = self.parser.parse(source)
        model = self.builder.build(arena, "javascript")
        state = {
            "imports": [
                {"module": i.module, "name": i.name, "local_name": i.local_name}
                for i in model.imports
            ],
            "definitions": [{"name": d.name, "kind": d.kind} for d in model.definitions],
            "calls": [
                {"name": c.name, "receiver": c.receiver, "full_name": c.full_name}
                for c in model.calls
            ],
        }
        assert state == snapshot
