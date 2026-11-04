#!/usr/bin/env bash
# Run static validation and eval cases against a real model (headless Claude Code).
# Examples:
#   ./scripts/eval.sh --static                          # no model calls
#   ./scripts/eval.sh --skill pr-review                 # regression set
#   ./scripts/eval.sh --skill pr-review --set adversarial --repeat 2
#   ./scripts/eval.sh --changed-since origin/main       # only skills you changed
# Exit codes: 0 pass, 1 a case or static check failed, 2 error (config, CLI, budget).
set -euo pipefail
exec "$(dirname "${BASH_SOURCE[0]}")/aitk" eval "$@"
