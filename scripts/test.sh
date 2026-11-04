#!/usr/bin/env bash
# Test the harness itself: Python unit tests (mock provider, temp fixtures), then shell
# integration tests in snapshot repos. No model calls, no network.
# Usage: test.sh [--python-only | --shell-only]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-all}"
status=0

if [ "$MODE" != --shell-only ]; then
  echo "== python unit tests"
  (cd "$ROOT/tests/python" && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q) || status=1
fi
if [ "$MODE" != --python-only ]; then
  for t in "$ROOT"/tests/shell/test_*.sh; do
    echo "== $(basename "$t")"
    out="$(bash "$t" 2>&1)"; rc=$?
    if [ $rc = 0 ]; then echo "$out" | tail -1; else echo "$out" | tail -25; status=1; fi
  done
fi
[ $status = 0 ] && echo "ALL TESTS PASSED" || echo "TESTS FAILED"
exit $status
