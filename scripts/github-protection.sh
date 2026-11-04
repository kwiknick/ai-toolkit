#!/usr/bin/env bash
# Configure and verify merge protection for the default branch with a GitHub ruleset.
#
# A failing GitHub Actions check does NOT block merging by itself. The repository
# rules must require it. This script prints, applies, or verifies a ruleset that
# requires: the `eval-gate` check (from GitHub Actions), a PR with 1 approving
# review including code owners, approval of the latest push, resolved review
# threads, and no force-push or deletion of the default branch.
#
# Usage: github-protection.sh print
#        github-protection.sh verify [--repo owner/name]     (read-only)
#        github-protection.sh apply  [--repo owner/name] --yes   (changes repo settings)
# Needs: gh (authenticated; apply needs admin on the repo), python3.
set -euo pipefail

ACTION="${1:-}"; shift || true
REPO=""; YES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --yes) YES=1; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
RULESET_NAME="ai-toolkit-quality-gate"
CHECK="eval-gate"
GITHUB_ACTIONS_APP_ID=15368   # pins the required check to GitHub Actions as its source

ruleset() {
  cat <<EOF
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "bypass_actors": [],
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": true,
      "require_last_push_approval": true,
      "required_review_thread_resolution": true
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "required_status_checks": [{"context": "$CHECK", "integration_id": $GITHUB_ACTIONS_APP_ID}]
    }}
  ]
}
EOF
}

repo() {
  [ -n "$REPO" ] && { echo "$REPO"; return; }
  gh repo view --json nameWithOwner --jq .nameWithOwner
}

case "$ACTION" in
  print) ruleset ;;
  apply)
    [ "$YES" = 1 ] || { echo "apply changes repository settings; rerun with --yes to confirm" >&2; exit 2; }
    r="$(repo)"
    existing="$(gh api "repos/$r/rulesets" --jq ".[] | select(.name == \"$RULESET_NAME\") | .id")"
    if [ -n "$existing" ]; then
      ruleset | gh api -X PUT "repos/$r/rulesets/$existing" --input - >/dev/null
      echo "updated ruleset $RULESET_NAME (#$existing) on $r"
    else
      ruleset | gh api -X POST "repos/$r/rulesets" --input - >/dev/null
      echo "created ruleset $RULESET_NAME on $r"
    fi
    echo "verify with: $0 verify --repo $r" ;;
  verify)
    if [ -n "${AITK_PROTECTION_FIXTURE:-}" ]; then
      # Offline test hook: a JSON array of effective branch rules.
      r="fixture"; branch="main"; rules="$(cat "$AITK_PROTECTION_FIXTURE")"; legacy='{}'
    else
      r="$(repo)"
      branch="$(gh api "repos/$r" --jq .default_branch)"
      # Effective rules on the branch, from every active ruleset (repo and org level).
      rules="$(gh api "repos/$r/rules/branches/$branch" 2>/dev/null)" || rules='[]'
      legacy="$(gh api "repos/$r/branches/$branch/protection" 2>/dev/null)" || legacy='{}'   # 404 = none
    fi
    RULES="$rules" LEGACY="$legacy" CHECK="$CHECK" REPO_NAME="$r" BRANCH="$branch" python3 - <<'EOF'
import json, os, sys
rules = json.loads(os.environ["RULES"] or "[]")
legacy = json.loads(os.environ["LEGACY"] or "{}")
check = os.environ["CHECK"]
by_type = {}
for rule in rules:
    by_type.setdefault(rule["type"], []).append(rule.get("parameters") or {})

def any_param(rule_type, pred):
    return any(pred(p) for p in by_type.get(rule_type, []))

lp = legacy.get("required_pull_request_reviews") or {}
lc = (legacy.get("required_status_checks") or {})
legacy_checks = set(lc.get("contexts") or []) | {c.get("context") for c in lc.get("checks") or []}
results = [
    ("required check '%s'" % check,
     any_param("required_status_checks", lambda p: any(c.get("context") == check for c in p.get("required_status_checks", [])))
     or check in legacy_checks),
    ("PR required with >= 1 approval",
     any_param("pull_request", lambda p: p.get("required_approving_review_count", 0) >= 1)
     or lp.get("required_approving_review_count", 0) >= 1),
    ("code owner review required",
     any_param("pull_request", lambda p: p.get("require_code_owner_review")) or lp.get("require_code_owner_reviews", False)),
    ("review threads must be resolved",
     any_param("pull_request", lambda p: p.get("required_review_thread_resolution"))
     or (legacy.get("required_conversation_resolution") or {}).get("enabled", False)),
    ("force pushes blocked", "non_fast_forward" in by_type
     or (legacy and not (legacy.get("allow_force_pushes") or {}).get("enabled", True))),
    ("branch deletion blocked", "deletion" in by_type
     or (legacy and not (legacy.get("allow_deletions") or {}).get("enabled", True))),
]
print(f"{os.environ['REPO_NAME']} @ {os.environ['BRANCH']}")
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
print("Note: admins and bypass actors can still override; review the ruleset's bypass list in Settings > Rules.")
sys.exit(0 if all(ok for _, ok in results) else 1)
EOF
    ;;
  *) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
