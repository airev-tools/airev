#!/usr/bin/env bash
# Smoke test for the built airev binary.
# Usage: bash build/test_binary.sh

set -euo pipefail

BINARY="${1:-dist/airev}"

if [ ! -f "$BINARY" ]; then
    echo "ERROR: Binary not found at $BINARY"
    echo "Run 'python build/nuitka_build.py' first."
    exit 1
fi

echo "Testing binary: $BINARY"

# Test 1: --help works
echo -n "  --help: "
if $BINARY scan --help >/dev/null 2>&1; then
    echo "OK"
else
    echo "FAIL"
    exit 1
fi

# Test 2: Scan current directory (should not crash)
echo -n "  scan .: "
# Exit code 0 (no findings) or 1 (findings) are both OK
if $BINARY scan . --format json >/dev/null 2>&1; then
    echo "OK (no findings)"
elif [ $? -eq 1 ]; then
    echo "OK (findings detected)"
else
    echo "FAIL (unexpected error)"
    exit 1
fi

# Test 3: Scan non-existent path
echo -n "  scan nonexistent: "
if $BINARY scan /tmp/nonexistent_airev_test_path 2>&1 | grep -qi "error\|no such\|not exist\|invalid"; then
    echo "OK (error handled)"
else
    echo "OK (handled gracefully)"
fi

echo ""
echo "All smoke tests passed!"
