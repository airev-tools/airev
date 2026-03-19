"""Tests for language capability layer."""

import pickle

from airev_core.languages.capabilities import LanguageCapabilities
from airev_core.languages.registry import (
    all_languages,
    all_supported_extensions,
    get_language_by_extension,
    get_language_by_id,
    register_language,
)


class TestLanguageRegistry:
    def test_python_by_extension(self) -> None:
        lang = get_language_by_extension(".py")
        assert lang is not None
        assert lang.language_id == "python"

    def test_js_by_extension(self) -> None:
        lang = get_language_by_extension(".js")
        assert lang is not None
        assert lang.language_id == "javascript"

    def test_ts_by_extension(self) -> None:
        lang = get_language_by_extension(".ts")
        assert lang is not None
        assert lang.language_id == "typescript"

    def test_tsx_by_extension(self) -> None:
        lang = get_language_by_extension(".tsx")
        assert lang is not None
        assert lang.language_id == "typescript"

    def test_unknown_extension(self) -> None:
        lang = get_language_by_extension(".rs")
        assert lang is None

    def test_get_by_id(self) -> None:
        lang = get_language_by_id("python")
        assert lang is not None
        assert ".py" in lang.file_extensions

    def test_unknown_id(self) -> None:
        assert get_language_by_id("rust") is None


class TestLanguageCapabilities:
    def test_python_supports_imports(self) -> None:
        lang = get_language_by_id("python")
        assert lang is not None
        assert lang.supports_imports
        assert lang.supports_comments
        assert "#" in lang.comment_prefixes

    def test_js_manifest_files(self) -> None:
        lang = get_language_by_id("javascript")
        assert lang is not None
        assert "package.json" in lang.manifest_files

    def test_ts_manifest_files(self) -> None:
        lang = get_language_by_id("typescript")
        assert lang is not None
        assert "tsconfig.json" in lang.manifest_files


class TestLanguageRegistration:
    def test_register_new_language(self) -> None:
        rust = LanguageCapabilities(
            language_id="rust",
            file_extensions=(".rs",),
            supports_comments=True,
            supports_imports=True,
            supports_string_literals=True,
            manifest_files=("Cargo.toml",),
            comment_prefixes=("//",),
        )
        register_language(rust)

        # Should now be discoverable
        assert get_language_by_id("rust") is not None
        assert get_language_by_extension(".rs") is not None
        assert ".rs" in all_supported_extensions()

    def test_all_languages_includes_builtins(self) -> None:
        langs = all_languages()
        lang_ids = {cap.language_id for cap in langs}
        assert "python" in lang_ids
        assert "javascript" in lang_ids
        assert "typescript" in lang_ids

    def test_all_supported_extensions(self) -> None:
        exts = all_supported_extensions()
        assert ".py" in exts
        assert ".js" in exts
        assert ".ts" in exts
        assert ".tsx" in exts


class TestPickleSafety:
    def test_capabilities_pickleable(self) -> None:
        lang = get_language_by_id("python")
        assert lang is not None
        rt = pickle.loads(pickle.dumps(lang))
        assert rt.language_id == "python"
        assert rt.file_extensions == lang.file_extensions
