#!/usr/bin/env bash
# Check that this machine can run the evals and the hardening skill.
# Prints PASS / WARN / FAIL lines and never prints secret values.
# Usage: doctor.sh [--online]   (--online also checks gh authentication)
# Exit codes: 0 no FAIL, 1 at least one FAIL.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ONLINE=0; [ "${1:-}" = --online ] && ONLINE=1
FAILS=0
pass() { printf '  PASS  %s\n' "$*"; }
warn() { printf '  WARN  %s\n' "$*"; }
fail() { printf '  FAIL  %s\n' "$*"; FAILS=$((FAILS + 1)); }
have() { command -v "$1" >/dev/null 2>&1; }

have git && pass "git $(git --version | awk '{print $3}')" || fail "git not found"
if have python3 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
  pass "python3 $(python3 -c 'import platform; print(platform.python_version())') (stdlib only)"
else fail "python3 >= 3.9 required"; fi
have claude && pass "Claude Code $(claude --version 2>/dev/null | head -1)" \
  || fail "claude CLI not found: evals run the real model through it"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then pass "ANTHROPIC_API_KEY is set (value not shown)"
elif [ "${CLAUDE_CODE_USE_BEDROCK:-}" = 1 ]; then pass "Claude Code is set to use Bedrock"
else warn "no ANTHROPIC_API_KEY: fine locally if 'claude' is logged in; CI needs it as a repo secret"; fi
if have gh; then
  pass "GitHub CLI $(gh --version | head -1 | awk '{print $3}')"
  [ "$ONLINE" = 1 ] && { gh auth status >/dev/null 2>&1 && pass "gh authenticated" || warn "gh not authenticated"; }
else warn "gh not found: needed to open hardening PRs and check branch protection"; fi
out="$(mktemp -d)"
if "$ROOT/scripts/eval.sh" --static --quiet --out "$out" >/dev/null 2>&1; then
  pass "static validation passes for all skills"
else fail "static validation fails: run ./scripts/eval.sh --static"; fi
rm -rf "$out"
for dir in "$ROOT"/claude/skills/*/; do
  name="$(basename "$dir")"; link="$HOME/.claude/skills/$name"
  if [ -L "$link" ] && [ "$(cd "$link" 2>/dev/null && pwd -P)" = "$(cd "$dir" && pwd -P)" ]; then
    pass "$name linked in ~/.claude/skills"
  else warn "$name not linked (see README, How to use, step 1)"; fi
done

printf '\n%d FAIL\n' "$FAILS"
[ "$FAILS" = 0 ]
