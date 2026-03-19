"""Curated database of deprecated APIs. Append-only — one line per entry."""

from __future__ import annotations

from dataclasses import dataclass

from airev_core.findings.models import Severity


@dataclass(slots=True, frozen=True)
class DeprecatedAPI:
    """A single deprecated API entry."""

    module: str
    name: str
    replacement: str
    reason: str
    severity: Severity
    language: str


DEPRECATED_APIS: tuple[DeprecatedAPI, ...] = (
    # --- Python stdlib ---
    DeprecatedAPI("os", "popen", "subprocess.run()", "Removed in 3.11", Severity.ERROR, "python"),
    DeprecatedAPI(
        "collections",
        "MutableMapping",
        "collections.abc.MutableMapping",
        "Removed in 3.10",
        Severity.ERROR,
        "python",
    ),
    DeprecatedAPI(
        "collections",
        "Mapping",
        "collections.abc.Mapping",
        "Removed in 3.10",
        Severity.ERROR,
        "python",
    ),
    DeprecatedAPI(
        "collections",
        "Sequence",
        "collections.abc.Sequence",
        "Removed in 3.10",
        Severity.ERROR,
        "python",
    ),
    DeprecatedAPI(
        "typing",
        "Optional",
        "X | None",
        "Deprecated since 3.9",
        Severity.WARNING,
        "python",
    ),
    DeprecatedAPI("typing", "Union", "X | Y", "Deprecated since 3.9", Severity.WARNING, "python"),
    DeprecatedAPI("typing", "List", "list[X]", "Deprecated since 3.9", Severity.WARNING, "python"),
    DeprecatedAPI(
        "typing", "Dict", "dict[K, V]", "Deprecated since 3.9", Severity.WARNING, "python"
    ),
    DeprecatedAPI(
        "typing", "Tuple", "tuple[X, ...]", "Deprecated since 3.9", Severity.WARNING, "python"
    ),
    DeprecatedAPI("typing", "Set", "set[X]", "Deprecated since 3.9", Severity.WARNING, "python"),
    DeprecatedAPI(
        "imp",
        "find_module",
        "importlib.util.find_spec()",
        "Removed in 3.12",
        Severity.ERROR,
        "python",
    ),
    DeprecatedAPI(
        "imp",
        "load_module",
        "importlib.util.module_from_spec()",
        "Removed in 3.12",
        Severity.ERROR,
        "python",
    ),
    DeprecatedAPI(
        "cgi", "parse", "urllib.parse.parse_qs()", "Removed in 3.13", Severity.ERROR, "python"
    ),
    DeprecatedAPI(
        "cgi",
        "FieldStorage",
        "multipart.MultipartParser",
        "Removed in 3.13",
        Severity.ERROR,
        "python",
    ),
    DeprecatedAPI(
        "distutils",
        "setup",
        "setuptools.setup()",
        "Removed in 3.12",
        Severity.ERROR,
        "python",
    ),
    DeprecatedAPI(
        "asyncio",
        "coroutine",
        "async def",
        "Removed in 3.11",
        Severity.ERROR,
        "python",
    ),
    DeprecatedAPI(
        "asyncio",
        "get_event_loop",
        "asyncio.get_running_loop()",
        "Deprecated since 3.10",
        Severity.WARNING,
        "python",
    ),
    DeprecatedAPI(
        "ssl",
        "wrap_socket",
        "SSLContext.wrap_socket()",
        "Removed in 3.12",
        Severity.ERROR,
        "python",
    ),
    # --- NumPy (commonly hallucinated) ---
    DeprecatedAPI("numpy", "bool", "numpy.bool_", "Removed in 1.24", Severity.ERROR, "python"),
    DeprecatedAPI("numpy", "int", "numpy.int_", "Removed in 1.24", Severity.ERROR, "python"),
    DeprecatedAPI("numpy", "float", "numpy.float64", "Removed in 1.24", Severity.ERROR, "python"),
    DeprecatedAPI(
        "numpy", "complex", "numpy.complex128", "Removed in 1.24", Severity.ERROR, "python"
    ),
    DeprecatedAPI("numpy", "object", "numpy.object_", "Removed in 1.24", Severity.ERROR, "python"),
    DeprecatedAPI("numpy", "str", "numpy.str_", "Removed in 1.24", Severity.ERROR, "python"),
    # --- Node.js ---
    DeprecatedAPI(
        "fs",
        "exists",
        "fs.existsSync() or fs.promises.access()",
        "Deprecated",
        Severity.WARNING,
        "javascript",
    ),
    DeprecatedAPI("url", "parse", "new URL()", "Deprecated", Severity.WARNING, "javascript"),
    DeprecatedAPI("url", "resolve", "new URL()", "Deprecated", Severity.WARNING, "javascript"),
    DeprecatedAPI(
        "querystring",
        "parse",
        "URLSearchParams",
        "Deprecated",
        Severity.WARNING,
        "javascript",
    ),
    DeprecatedAPI(
        "querystring",
        "stringify",
        "URLSearchParams",
        "Deprecated",
        Severity.WARNING,
        "javascript",
    ),
    DeprecatedAPI(
        "Buffer",
        "Buffer",
        "Buffer.from() or Buffer.alloc()",
        "Deprecated — security risk",
        Severity.ERROR,
        "javascript",
    ),
    DeprecatedAPI(
        "crypto",
        "createCipher",
        "crypto.createCipheriv()",
        "Deprecated — insecure",
        Severity.ERROR,
        "javascript",
    ),
    DeprecatedAPI(
        "crypto",
        "createDecipher",
        "crypto.createDecipheriv()",
        "Deprecated — insecure",
        Severity.ERROR,
        "javascript",
    ),
)

# Build lookup index: (module, name) -> DeprecatedAPI for O(1) access
DEPRECATED_INDEX: dict[tuple[str, str], DeprecatedAPI] = {
    (entry.module, entry.name): entry for entry in DEPRECATED_APIS
}
