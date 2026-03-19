"""Tests for StringTable."""

import pickle

from airev_core.arena.string_table import StringTable


class TestStringTable:
    def test_intern_returns_index(self) -> None:
        st = StringTable()
        idx = st.intern("hello")
        assert idx == 0

    def test_intern_same_string_returns_same_index(self) -> None:
        st = StringTable()
        a = st.intern("hello")
        b = st.intern("hello")
        assert a == b

    def test_different_strings_get_different_indices(self) -> None:
        st = StringTable()
        a = st.intern("hello")
        b = st.intern("world")
        assert a != b

    def test_get_returns_correct_string(self) -> None:
        st = StringTable()
        st.intern("alpha")
        st.intern("beta")
        assert st.get(0) == "alpha"
        assert st.get(1) == "beta"

    def test_count_property(self) -> None:
        st = StringTable()
        assert st.count == 0
        st.intern("a")
        assert st.count == 1
        st.intern("b")
        assert st.count == 2
        st.intern("a")  # duplicate
        assert st.count == 2

    def test_pickle_roundtrip(self) -> None:
        st = StringTable()
        st.intern("foo")
        st.intern("bar")
        st.intern("baz")

        restored = pickle.loads(pickle.dumps(st))
        assert restored.count == 3
        assert restored.get(0) == "foo"
        assert restored.get(1) == "bar"
        assert restored.get(2) == "baz"
        # Re-interning should return existing indices
        assert restored.intern("foo") == 0
        assert restored.intern("new") == 3
