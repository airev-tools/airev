"""Tests for UastArena."""

import pickle

import numpy as np

from airev_core.arena import UastArena
from airev_core.arena.node_types import TYPE_CALL, TYPE_FUNCTION_DEF, TYPE_IMPORT, TYPE_MODULE


class TestUastArena:
    def test_allocate_and_read_properties(self) -> None:
        arena = UastArena(capacity=10)
        idx = arena.allocate(
            node_type=TYPE_MODULE,
            start_byte=0,
            end_byte=100,
            start_line=1,
            start_col=0,
            name="test_module",
        )
        assert idx == 0
        assert arena.node_types[idx] == TYPE_MODULE
        assert arena.start_bytes[idx] == 0
        assert arena.end_bytes[idx] == 100
        assert arena.start_lines[idx] == 1
        assert arena.start_cols[idx] == 0

    def test_tree_linkage(self) -> None:
        arena = UastArena(capacity=20)
        root = arena.allocate(TYPE_MODULE, 0, 100, 1, 0, name="root")
        child1 = arena.allocate(TYPE_IMPORT, 0, 20, 1, 0, parent=root, name="os")
        child2 = arena.allocate(TYPE_FUNCTION_DEF, 21, 80, 3, 0, parent=root, name="hello")
        grandchild = arena.allocate(TYPE_CALL, 30, 50, 4, 4, parent=child2, name="print")

        assert arena.get_children(root) == [child1, child2]
        assert arena.get_children(child2) == [grandchild]
        assert arena.get_children(child1) == []
        assert arena.parent_indices[child1] == root
        assert arena.parent_indices[grandchild] == child2

    def test_auto_grow(self) -> None:
        arena = UastArena(capacity=100)
        for i in range(200):
            arena.allocate(TYPE_MODULE, i, i + 1, i + 1, 0)
        assert arena.count == 200
        assert arena.node_types[199] == TYPE_MODULE

    def test_get_name(self) -> None:
        arena = UastArena(capacity=10)
        idx = arena.allocate(TYPE_FUNCTION_DEF, 0, 50, 1, 0, name="my_func")
        unnamed = arena.allocate(TYPE_CALL, 10, 20, 2, 0)
        assert arena.get_name(idx) == "my_func"
        assert arena.get_name(unnamed) is None

    def test_get_children_returns_correct_indices(self) -> None:
        arena = UastArena(capacity=10)
        parent = arena.allocate(TYPE_MODULE, 0, 100, 1, 0)
        c1 = arena.allocate(TYPE_IMPORT, 0, 10, 1, 0, parent=parent)
        c2 = arena.allocate(TYPE_IMPORT, 11, 20, 2, 0, parent=parent)
        c3 = arena.allocate(TYPE_FUNCTION_DEF, 21, 80, 3, 0, parent=parent)
        assert arena.get_children(parent) == [c1, c2, c3]

    def test_count_property(self) -> None:
        arena = UastArena(capacity=10)
        assert arena.count == 0
        arena.allocate(TYPE_MODULE, 0, 10, 1, 0)
        assert arena.count == 1
        arena.allocate(TYPE_IMPORT, 0, 5, 1, 0)
        assert arena.count == 2

    def test_empty_arena(self) -> None:
        arena = UastArena(capacity=10)
        assert arena.count == 0
        assert arena.get_children(0) == []

    def test_pickle_roundtrip(self) -> None:
        arena = UastArena(capacity=50)
        root = arena.allocate(TYPE_MODULE, 0, 100, 1, 0, name="module")
        arena.allocate(TYPE_IMPORT, 0, 20, 1, 0, parent=root, name="os")
        arena.allocate(TYPE_FUNCTION_DEF, 21, 80, 3, 0, parent=root, name="hello")
        arena.cst_backlinks.append("fake_cst_node")

        restored = pickle.loads(pickle.dumps(arena))

        assert restored.count == 3
        assert np.array_equal(
            restored.node_types[: restored.count],
            arena.node_types[: arena.count],
        )
        assert restored.get_name(0) == "module"
        assert restored.get_name(1) == "os"
        assert restored.get_name(2) == "hello"
        assert restored.strings.count == 3
        assert restored.get_children(0) == [1, 2]
        # cst_backlinks should be reset
        assert restored.cst_backlinks == []

    def test_snapshot_small_tree(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        arena = UastArena(capacity=10)
        root = arena.allocate(TYPE_MODULE, 0, 100, 1, 0, name="module")
        arena.allocate(TYPE_IMPORT, 0, 10, 1, 0, parent=root, name="os")
        fn = arena.allocate(TYPE_FUNCTION_DEF, 11, 80, 3, 0, parent=root, name="hello")
        arena.allocate(TYPE_CALL, 20, 40, 4, 4, parent=fn, name="print")

        state = {
            "count": arena.count,
            "node_types": arena.node_types[: arena.count].tolist(),
            "names": [arena.get_name(i) for i in range(arena.count)],
            "children": {i: arena.get_children(i) for i in range(arena.count)},
        }
        assert state == snapshot
