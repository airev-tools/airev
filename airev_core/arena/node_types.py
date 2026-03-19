"""UAST Node Type Constants.

These are integer keys used in the numpy arena and dispatch tables.
"""

TYPE_MODULE: int = 0
TYPE_IMPORT: int = 1
TYPE_IMPORT_FROM: int = 2
TYPE_FUNCTION_DEF: int = 3
TYPE_CLASS_DEF: int = 4
TYPE_CALL: int = 5
TYPE_ASSIGNMENT: int = 6
TYPE_DECORATOR: int = 7
TYPE_RETURN: int = 8
TYPE_IF: int = 9
TYPE_FOR: int = 10
TYPE_WHILE: int = 11
TYPE_TRY: int = 12
TYPE_EXCEPT: int = 13
TYPE_WITH: int = 14
TYPE_RAISE: int = 15
TYPE_ASSERT: int = 16
TYPE_YIELD: int = 17
TYPE_AWAIT: int = 18
TYPE_STRING_LITERAL: int = 19
TYPE_VARIABLE_REF: int = 20
TYPE_ATTRIBUTE_ACCESS: int = 21
TYPE_SUBSCRIPT: int = 22
TYPE_BINARY_OP: int = 23
TYPE_UNARY_OP: int = 24
TYPE_COMPARISON: int = 25
TYPE_BOOLEAN_OP: int = 26
TYPE_LAMBDA: int = 27
TYPE_DICT: int = 28
TYPE_LIST: int = 29
TYPE_TUPLE: int = 30
TYPE_SET: int = 31
TYPE_UNKNOWN: int = 99

# All node type constants for iteration and validation
_ALL_TYPES: dict[str, int] = {
    k: v for k, v in globals().items() if isinstance(v, int) and k.startswith("TYPE_")
}

# Reverse mapping for debug/display
NODE_TYPE_NAMES: dict[int, str] = {v: k for k, v in _ALL_TYPES.items()}
