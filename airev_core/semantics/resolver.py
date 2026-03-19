"""Import resolver — determines if imported modules exist.

Full implementation in Task 3.
"""

from __future__ import annotations


class ImportResolver:
    """Resolves import statements to determine if packages/modules exist."""

    def module_exists(self, module_name: str) -> bool:
        """Return True if the module can be resolved to a real package/file."""
        raise NotImplementedError
