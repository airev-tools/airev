"""Language registry — centralizes language metadata for the engine.

New languages are added by registering LanguageCapabilities here.
The engine, config loader, file discovery, and resolver all query this
registry instead of hardcoding language-specific logic.
"""

from __future__ import annotations

from airev_core.languages.capabilities import LanguageCapabilities

# Built-in language definitions
PYTHON = LanguageCapabilities(
    language_id="python",
    file_extensions=(".py",),
    supports_comments=True,
    supports_imports=True,
    supports_string_literals=True,
    manifest_files=("pyproject.toml", "setup.cfg", "requirements.txt"),
    comment_prefixes=("#",),
)

JAVASCRIPT = LanguageCapabilities(
    language_id="javascript",
    file_extensions=(".js", ".jsx", ".mjs", ".cjs"),
    supports_comments=True,
    supports_imports=True,
    supports_string_literals=True,
    manifest_files=("package.json",),
    comment_prefixes=("//",),
)

TYPESCRIPT = LanguageCapabilities(
    language_id="typescript",
    file_extensions=(".ts", ".tsx"),
    supports_comments=True,
    supports_imports=True,
    supports_string_literals=True,
    manifest_files=("package.json", "tsconfig.json"),
    comment_prefixes=("//",),
)

# Registry: maps language_id → capabilities
_REGISTRY: dict[str, LanguageCapabilities] = {
    "python": PYTHON,
    "javascript": JAVASCRIPT,
    "typescript": TYPESCRIPT,
}

# Extension → language_id lookup
_EXTENSION_MAP: dict[str, str] = {}
for _lang in _REGISTRY.values():
    for _ext in _lang.file_extensions:
        _EXTENSION_MAP[_ext] = _lang.language_id


def register_language(caps: LanguageCapabilities) -> None:
    """Register a new language's capabilities.

    This is the extension point for adding new languages without
    modifying core engine code.
    """
    _REGISTRY[caps.language_id] = caps
    for ext in caps.file_extensions:
        _EXTENSION_MAP[ext] = caps.language_id


def get_language_by_id(language_id: str) -> LanguageCapabilities | None:
    """Return capabilities for a known language, or None."""
    return _REGISTRY.get(language_id)


def get_language_by_extension(ext: str) -> LanguageCapabilities | None:
    """Return capabilities for a file extension, or None."""
    lang_id = _EXTENSION_MAP.get(ext)
    if lang_id is None:
        return None
    return _REGISTRY.get(lang_id)


def all_supported_extensions() -> frozenset[str]:
    """Return all registered file extensions."""
    return frozenset(_EXTENSION_MAP.keys())


def all_languages() -> list[LanguageCapabilities]:
    """Return all registered languages."""
    return list(_REGISTRY.values())
