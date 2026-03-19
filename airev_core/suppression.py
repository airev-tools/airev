"""Inline suppression — parse `# airev: ignore[rule-id]` comments.

Suppression is applied OUTSIDE rule evaluation bodies.
Rules remain pure functions that know nothing about suppression.
"""

from __future__ import annotations

import re

# Matches:  # airev: ignore[rule-id]  or  # airev: ignore[rule-a, rule-b]  or  # airev: ignore
# Also supports //  for JS/TS line comments
_IGNORE_RE = re.compile(
    r"(?:#|//)\s*airev:\s*ignore"
    r"(?:\[([a-z][a-z0-9\-]*(?:\s*,\s*[a-z][a-z0-9\-]*)*)\])?"
)


def parse_ignore_directive(comment_text: str) -> tuple[bool, frozenset[str]]:
    """Parse a single comment for an airev ignore directive.

    Returns (has_directive, rule_ids).
    If has_directive is True and rule_ids is empty, all rules are suppressed.
    """
    m = _IGNORE_RE.search(comment_text)
    if m is None:
        return False, frozenset()

    rule_list = m.group(1)
    if rule_list is None:
        # Bare `airev: ignore` — suppress all rules on this line
        return True, frozenset()

    rule_ids = frozenset(r.strip() for r in rule_list.split(",") if r.strip())
    return True, rule_ids


def build_suppression_map(
    source: bytes,
    language: str,
) -> dict[int, frozenset[str]]:
    """Build a mapping of line_number -> suppressed rule IDs.

    An empty frozenset means ALL rules are suppressed on that line.
    Only real comments are parsed — directives inside string literals are ignored
    by scanning for comment tokens with a simple heuristic.

    Args:
        source: The raw source bytes.
        language: 'python', 'javascript', or 'typescript'.

    Returns:
        Dict mapping 1-based line numbers to suppressed rule IDs.
    """
    suppression_map: dict[int, frozenset[str]] = {}

    try:
        text = source.decode("utf-8", errors="replace")
    except Exception:
        return suppression_map

    lines = text.splitlines()

    for line_idx, line in enumerate(lines):
        line_no = line_idx + 1

        # Find comment start — simple heuristic that avoids parsing strings fully
        comment_start = _find_comment_start(line, language)
        if comment_start < 0:
            continue

        comment_text = line[comment_start:]
        has_directive, rule_ids = parse_ignore_directive(comment_text)
        if has_directive:
            suppression_map[line_no] = rule_ids

    return suppression_map


def _find_comment_start(line: str, language: str) -> int:
    """Find the index of a comment in a line, ignoring comments inside strings.

    Returns -1 if no comment found.
    """
    in_single_quote = False
    in_double_quote = False
    in_template = False
    i = 0
    length = len(line)

    while i < length:
        ch = line[i]

        # Handle escape sequences inside strings
        if (in_single_quote or in_double_quote or in_template) and ch == "\\":
            i += 2  # Skip escaped char
            continue

        # Toggle string state
        if ch == "'" and not in_double_quote and not in_template:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote and not in_template:
            in_double_quote = not in_double_quote
        elif ch == "`" and language in ("javascript", "typescript"):
            if not in_single_quote and not in_double_quote:
                in_template = not in_template

        # Check for comment start outside strings
        elif not in_single_quote and not in_double_quote and not in_template:
            if language == "python" and ch == "#":
                return i
            if (
                language in ("javascript", "typescript")
                and ch == "/"
                and i + 1 < length
                and line[i + 1] == "/"
            ):
                return i

        i += 1

    return -1


def is_finding_suppressed(
    suppression_map: dict[int, frozenset[str]],
    rule_id: str,
    line: int,
) -> bool:
    """Check if a finding at the given line is suppressed.

    Args:
        suppression_map: Output of build_suppression_map().
        rule_id: The rule ID to check.
        line: 1-based line number of the finding.

    Returns:
        True if the finding should be suppressed.
    """
    suppressed = suppression_map.get(line)
    if suppressed is None:
        return False

    # Empty set means ALL rules suppressed
    if not suppressed:
        return True

    return rule_id in suppressed
