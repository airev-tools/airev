"""Regex and entropy-based pattern detection heuristics."""

from __future__ import annotations

import math


def shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of a string.

    Pure function. Higher values indicate more randomness.
    Typical thresholds: >4.5 suggests a secret/token.
    """
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())
