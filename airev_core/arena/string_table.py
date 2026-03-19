"""Interned string storage for identifiers and names.

Arena nodes reference strings by integer index, keeping arrays purely numeric.
"""


class StringTable:
    """Interned string storage. Deduplicates identical identifiers."""

    __slots__ = ("_strings", "_index")

    def __init__(self) -> None:
        self._strings: list[str] = []
        self._index: dict[str, int] = {}

    def intern(self, s: str) -> int:
        """Return the index of the string, interning it if new."""
        idx = self._index.get(s)
        if idx is not None:
            return idx
        idx = len(self._strings)
        self._strings.append(s)
        self._index[s] = idx
        return idx

    def get(self, idx: int) -> str:
        """Retrieve string by index."""
        return self._strings[idx]

    @property
    def count(self) -> int:
        """Number of interned strings."""
        return len(self._strings)
