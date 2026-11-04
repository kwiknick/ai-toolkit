#!/usr/bin/env bash
# Scaffold a skill: claude/skills/<name>/SKILL.md, evals/<name>/spec.json, one regression case.
# Usage: ./scripts/new-skill.sh <name> --description "What it does. Use when ..."
set -euo pipefail
exec "$(dirname "${BASH_SOURCE[0]}")/aitk" new-skill "$@"
