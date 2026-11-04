# Minimal assertion helpers for shell tests. Source from a test script.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}"/aitk-test.XXXXXX)"; TMP="$(cd "$TMP" && pwd)"
trap 'rm -rf "$TMP"' EXIT
PASS=0

# Deterministic git identity for temp repos only.
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.invalid
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=init.defaultBranch GIT_CONFIG_VALUE_0=main
export GIT_CONFIG_NOSYSTEM=1

ok() { PASS=$((PASS + 1)); echo "  ok - $*"; }
fail() { echo "  FAIL - $*" >&2; exit 1; }
assert_eq() { [ "$1" = "$2" ] && ok "$3" || fail "$3: expected '$2', got '$1'"; }
assert_contains() { case "$1" in *"$2"*) ok "$3" ;; *) fail "$3: '$2' not in output: $1" ;; esac; }
assert_not_contains() { case "$1" in *"$2"*) fail "$3: '$2' unexpectedly in output" ;; *) ok "$3" ;; esac; }
# assert_exit <code> <description> -- <command...>
assert_exit() {
  local want="$1" desc="$2"; shift 3
  set +e; OUT="$("$@" 2>&1)"; local got=$?; set -e
  [ "$got" = "$want" ] && ok "$desc (exit $got)" || fail "$desc: exit $got, want $want. Output: $OUT"
}
done_tests() { echo "$(basename "$0"): $PASS checks passed"; }

# Snapshot the toolkit working tree into a fresh git repo at $1 (no .git, no outputs).
snapshot_toolkit() {
  mkdir -p "$1"
  (cd "$ROOT" && tar --exclude ./.git --exclude ./.aitk --exclude ./raw_files --exclude ./tasks \
     --exclude ./docs/specs --exclude ./docs/plans --exclude '*/__pycache__' -cf - .) | (cd "$1" && tar -xf -)
  git -C "$1" init -q
  git -C "$1" add -A
  git -C "$1" commit -qm "toolkit snapshot"
}
