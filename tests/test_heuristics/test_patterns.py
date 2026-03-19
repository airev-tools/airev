"""Tests for Shannon entropy and pattern heuristics."""

from __future__ import annotations

import math

import pytest

from airev_core.heuristics.patterns import shannon_entropy


class TestShannonEntropy:
    """Unit tests for the Shannon entropy function."""

    def test_empty_string(self) -> None:
        assert shannon_entropy("") == 0.0

    def test_single_character(self) -> None:
        assert shannon_entropy("a") == 0.0

    def test_repeated_character(self) -> None:
        assert shannon_entropy("aaaaaaa") == 0.0

    def test_two_equal_chars(self) -> None:
        result = shannon_entropy("ab")
        assert result == pytest.approx(1.0)

    def test_four_equal_chars(self) -> None:
        result = shannon_entropy("abcd")
        assert result == pytest.approx(2.0)

    def test_high_entropy_random_string(self) -> None:
        # A string with many unique characters should have high entropy
        value = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
        result = shannon_entropy(value)
        assert result > 3.5

    def test_low_entropy_repeated_pattern(self) -> None:
        value = "aaaaabbbbbccccc"
        result = shannon_entropy(value)
        expected = -(3 * (5 / 15) * math.log2(5 / 15))
        assert result == pytest.approx(expected)

    def test_typical_api_key_high_entropy(self) -> None:
        # Real API keys typically have entropy > 4.5
        key = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert shannon_entropy(key) > 4.0

    def test_placeholder_low_entropy(self) -> None:
        assert shannon_entropy("your-api-key-here") < 4.0

    def test_pure_function(self) -> None:
        """Same input always produces same output."""
        s = "test_entropy_value_12345"
        assert shannon_entropy(s) == shannon_entropy(s)
