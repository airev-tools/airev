"""Tests for UAST node type constants."""

import pickle

from airev_core.arena.node_types import (
    _ALL_TYPES,
    NODE_TYPE_NAMES,
    TYPE_CALL,
    TYPE_FUNCTION_DEF,
    TYPE_MODULE,
    TYPE_UNKNOWN,
)


class TestNodeTypeConstants:
    def test_all_constants_are_integers(self) -> None:
        for name, value in _ALL_TYPES.items():
            assert isinstance(value, int), f"{name} is not an int"

    def test_all_constants_are_unique(self) -> None:
        values = list(_ALL_TYPES.values())
        assert len(values) == len(set(values)), "Duplicate node type values found"

    def test_node_type_names_maps_correctly(self) -> None:
        assert NODE_TYPE_NAMES[0] == "TYPE_MODULE"
        assert NODE_TYPE_NAMES[5] == "TYPE_CALL"
        assert NODE_TYPE_NAMES[99] == "TYPE_UNKNOWN"

    def test_reverse_mapping_covers_all_constants(self) -> None:
        assert len(NODE_TYPE_NAMES) == len(_ALL_TYPES)

    def test_known_constants_have_expected_values(self) -> None:
        assert TYPE_MODULE == 0
        assert TYPE_FUNCTION_DEF == 3
        assert TYPE_CALL == 5
        assert TYPE_UNKNOWN == 99

    def test_node_type_names_pickle_roundtrip(self) -> None:
        restored = pickle.loads(pickle.dumps(NODE_TYPE_NAMES))
        assert restored == NODE_TYPE_NAMES
