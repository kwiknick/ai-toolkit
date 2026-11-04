#!/usr/bin/env bash
# The ruleset we apply must satisfy our own verifier; weaker rules must not. Offline.
source "$(dirname "$0")/lib.sh"
GP="$ROOT/scripts/github-protection.sh"
"$GP" print | python3 -c 'import json,sys; json.dump(json.load(sys.stdin)["rules"], open(sys.argv[1], "w"))' "$TMP/full.json"
assert_exit 0 "applied ruleset verifies" -- env AITK_PROTECTION_FIXTURE="$TMP/full.json" "$GP" verify
python3 - "$TMP/full.json" "$TMP/weak.json" <<'PY'
import json, sys
rules = [r for r in json.load(open(sys.argv[1])) if r["type"] != "required_status_checks"]
json.dump(rules, open(sys.argv[2], "w"))
PY
assert_exit 1 "missing required check fails verify" -- env AITK_PROTECTION_FIXTURE="$TMP/weak.json" "$GP" verify
assert_contains "$OUT" "FAIL  required check 'eval-gate'" "names the missing check"
echo '[]' > "$TMP/none.json"
assert_exit 1 "no rules fails verify" -- env AITK_PROTECTION_FIXTURE="$TMP/none.json" "$GP" verify
assert_exit 2 "apply requires --yes" -- "$GP" apply --repo example/example
# The required check name must match the workflow job name.
assert_contains "$(cat "$ROOT/.github/workflows/eval-pr.yml")" "name: eval-gate" "workflow job is named eval-gate"
done_tests
