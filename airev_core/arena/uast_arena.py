"""Structure of Arrays storage for UAST nodes.

Nodes are integer indices into parallel numpy arrays. This gives contiguous
memory access and ~10x traversal speed over object-based trees.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from airev_core.arena.string_table import StringTable

if TYPE_CHECKING:
    from numpy.typing import NDArray

_SENTINEL: int = -1
_TREE_ATTRS = (
    "parent_indices",
    "first_child",
    "next_sibling",
    "name_indices",
)
_ALL_ARRAY_ATTRS = (
    "node_types",
    "start_bytes",
    "end_bytes",
    "start_lines",
    "start_cols",
    *_TREE_ATTRS,
)


class UastArena:
    """Structure of Arrays storage for UAST nodes. Mimics a bump-allocated arena."""

    __slots__ = (
        "node_types",
        "start_bytes",
        "end_bytes",
        "start_lines",
        "start_cols",
        "parent_indices",
        "first_child",
        "next_sibling",
        "name_indices",
        "strings",
        "cst_backlinks",
        "_count",
        "_capacity",
    )

    def __init__(self, capacity: int = 100_000) -> None:
        self.node_types: NDArray[np.int32] = np.zeros(capacity, dtype=np.int32)
        self.start_bytes: NDArray[np.int32] = np.zeros(capacity, dtype=np.int32)
        self.end_bytes: NDArray[np.int32] = np.zeros(capacity, dtype=np.int32)
        self.start_lines: NDArray[np.int32] = np.zeros(capacity, dtype=np.int32)
        self.start_cols: NDArray[np.int32] = np.zeros(capacity, dtype=np.int32)

        self.parent_indices: NDArray[np.int32] = np.full(capacity, _SENTINEL, dtype=np.int32)
        self.first_child: NDArray[np.int32] = np.full(capacity, _SENTINEL, dtype=np.int32)
        self.next_sibling: NDArray[np.int32] = np.full(capacity, _SENTINEL, dtype=np.int32)
        self.name_indices: NDArray[np.int32] = np.full(capacity, _SENTINEL, dtype=np.int32)

        self.strings = StringTable()
        self.cst_backlinks: list[Any] = []

        self._count: int = 0
        self._capacity: int = capacity

    @property
    def count(self) -> int:
        """Number of allocated nodes."""
        return self._count

    def allocate(
        self,
        node_type: int,
        start_byte: int,
        end_byte: int,
        start_line: int,
        start_col: int,
        parent: int = _SENTINEL,
        name: str | None = None,
    ) -> int:
        """Allocate a node. Returns its index. O(1) bump allocation."""
        if self._count >= self._capacity:
            self._grow()

        idx = self._count
        self.node_types[idx] = node_type
        self.start_bytes[idx] = start_byte
        self.end_bytes[idx] = end_byte
        self.start_lines[idx] = start_line
        self.start_cols[idx] = start_col
        self.parent_indices[idx] = parent

        if name is not None:
            self.name_indices[idx] = self.strings.intern(name)

        # Link as child of parent
        if parent != _SENTINEL:
            if self.first_child[parent] == _SENTINEL:
                self.first_child[parent] = idx
            else:
                # Walk to last sibling and append
                sib = int(self.first_child[parent])
                while self.next_sibling[sib] != _SENTINEL:
                    sib = int(self.next_sibling[sib])
                self.next_sibling[sib] = idx

        self._count += 1
        return idx

    def get_name(self, idx: int) -> str | None:
        """Return the name string for a node, or None if unnamed."""
        name_idx = int(self.name_indices[idx])
        if name_idx == _SENTINEL:
            return None
        return self.strings.get(name_idx)

    def get_children(self, idx: int) -> list[int]:
        """Return indices of all children of a node."""
        children: list[int] = []
        child = int(self.first_child[idx])
        while child != _SENTINEL:
            children.append(child)
            child = int(self.next_sibling[child])
        return children

    def _grow(self) -> None:
        """Double capacity when exhausted."""
        new_cap = self._capacity * 2
        for attr in _ALL_ARRAY_ATTRS:
            old: NDArray[np.int32] = getattr(self, attr)
            if attr in _TREE_ATTRS:
                new = np.full(new_cap, _SENTINEL, dtype=np.int32)
            else:
                new = np.zeros(new_cap, dtype=np.int32)
            new[: self._capacity] = old
            setattr(self, attr, new)
        self._capacity = new_cap

    def __getstate__(self) -> dict[str, Any]:
        """Exclude cst_backlinks during pickling (Tree-sitter nodes are C pointers)."""
        return {attr: getattr(self, attr) for attr in self.__slots__ if attr != "cst_backlinks"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state and reset cst_backlinks to empty list."""
        for attr, value in state.items():
            object.__setattr__(self, attr, value)
        object.__setattr__(self, "cst_backlinks", [])
