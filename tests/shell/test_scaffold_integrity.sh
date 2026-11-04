#!/usr/bin/env bash
# Scaffold a skill, check it validates, and check the append-only rule on evals/ end to end.
# Runs in a snapshot repo so the real checkout is never touched. No model calls.
source "$(dirname "$0")/lib.sh"
TK="$TMP/toolkit"; snapshot_toolkit "$TK"; cd "$TK"

# --- scaffolding ---------------------------------------------------------------
assert_exit 0 "scaffold a skill" -- ./scripts/new-skill.sh demo-skill --description "Demo skill. Use when testing."
for f in claude/skills/demo-skill/SKILL.md evals/demo-skill/spec.json \
         evals/demo-skill/cases/regression/demo-skill-example-001.json; do
  [ -f "$f" ] && ok "created $f" || fail "missing $f"
done
assert_exit 0 "scaffolded skill passes static validation" -- ./scripts/eval.sh --skill demo-skill --static --quiet
assert_exit 2 "duplicate scaffold refused" -- ./scripts/new-skill.sh demo-skill --description x
assert_exit 2 "bad name refused" -- ./scripts/new-skill.sh "Bad_Name" --description x
assert_exit 0 "new files under evals/ pass integrity" -- ./scripts/aitk integrity --base HEAD
git add -A && git -c core.hooksPath=/dev/null commit -qm "add demo-skill"

# --- static validation catches a skill with no evals -------------------------------
rm -rf evals/demo-skill
assert_exit 1 "skill without evals fails static validation" -- ./scripts/eval.sh --static --quiet
git checkout -q -- evals/

# --- append-only evals/ ------------------------------------------------------------
CASE=evals/pr-review/cases/regression/pr-review-logic-off-by-one-001.json
python3 - "$CASE" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["assertions"] = d["assertions"][:1]; json.dump(d, open(p, "w"), indent=2)
PY
assert_exit 1 "weakened regression case is a violation" -- ./scripts/aitk integrity --base HEAD
assert_contains "$OUT" "VIOLATION: $CASE: modified" "names the modified case"
assert_exit 0 "label override downgrades it" -- ./scripts/aitk integrity --base HEAD --allow-criteria-change
git checkout -q -- evals/

ADV=evals/pr-review/cases/adversarial/pr-review-conflicting-scope-001.json
git mv "$ADV" evals/pr-review/cases/regression/
assert_exit 0 "unchanged promotion adversarial -> regression is allowed" -- ./scripts/aitk integrity --base HEAD
assert_contains "$OUT" "promoted" "recognized as a promotion"
git reset -q --hard

python3 - <<'PY'
import json
p = "evals/pr-review/spec.json"; d = json.load(open(p)); d["version"] = "1.0.1"; json.dump(d, open(p, "w"), indent=2)
PY
assert_exit 0 "spec.json version bump is allowed" -- ./scripts/aitk integrity --base HEAD
python3 - <<'PY'
import json
p = "evals/pr-review/spec.json"; d = json.load(open(p)); d["fixable_files"].append("SKILL.md"); json.dump(d, open(p, "w"), indent=2)
PY
assert_exit 1 "widening fixable_files is a violation" -- ./scripts/aitk integrity --base HEAD
git reset -q --hard

# --- --changed-since picks only touched skills ----------------------------------------
echo "<!-- edit -->" >> claude/skills/onboard-tool/SKILL.md
assert_exit 0 "changed-since runs static for the touched skill only" -- ./scripts/eval.sh --changed-since HEAD --static --quiet
assert_contains "$OUT" "skills changed since HEAD: onboard-tool" "only onboard-tool selected"
git reset -q --hard
done_tests
