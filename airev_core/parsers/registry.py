"""Parser registry — routes files to the correct language parser by extension."""

from __future__ import annotations

from airev_core.parsers.python_parser import PythonParser
from airev_core.parsers.typescript_parser import JavaScriptParser, TypeScriptParser

_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


class ParserRegistry:
    """Routes files to the correct language parser based on extension."""

    __slots__ = ("_parsers",)

    def __init__(self) -> None:
        self._parsers: dict[str, PythonParser | JavaScriptParser | TypeScriptParser] = {}

    def get_parser(
        self, file_path: str
    ) -> PythonParser | JavaScriptParser | TypeScriptParser | None:
        """Return the appropriate parser for the file, or None if unsupported."""
        language = self.get_language(file_path)
        if language is None:
            return None

        if language not in self._parsers:
            if language == "python":
                self._parsers[language] = PythonParser()
            elif language == "javascript":
                self._parsers[language] = JavaScriptParser()
            elif language == "typescript":
                self._parsers[language] = TypeScriptParser()

        return self._parsers.get(language)

    def get_language(self, file_path: str) -> str | None:
        """Return 'python', 'javascript', 'typescript', or None."""
        dot_idx = file_path.rfind(".")
        if dot_idx == -1:
            return None
        ext = file_path[dot_idx:]
        return _EXTENSION_TO_LANGUAGE.get(ext)

    @property
    def supported_extensions(self) -> frozenset[str]:
        """All file extensions this registry can handle."""
        return frozenset(_EXTENSION_TO_LANGUAGE.keys())
