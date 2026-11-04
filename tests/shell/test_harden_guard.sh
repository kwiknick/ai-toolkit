#!/usr/bin/env bash
# The weekly workflow's path guard (the exact `run:` block from harden-scheduled.yml)
# accepts what /harden-skill is allowed to change and refuses everything else.
source "$(dirname "$0")/lib.sh"
command -v jq >/dev/null || { echo "jq not installed, skipping"; exit 0; }
TK="$TMP/toolkit"; snapshot_toolkit "$TK"; cd "$TK"

# Pull the guard step's shell out of the workflow, so the test runs the real code.
python3 - .github/workflows/harden-scheduled.yml "$TMP/guard.sh" <<'PY'
import sys
lines = open(sys.argv[1]).read().splitlines()
i = next(n for n, l in enumerate(lines) if "name: Apply the patch and check paths" in l)
i = next(n for n in range(i, len(lines)) if lines[n].strip() == "run: |") + 1
indent = len(lines[i]) - len(lines[i].lstrip())
body = []
for l in lines[i:]:
    if l.strip() and len(l) - len(l.lstrip()) < indent:
        break
    body.append(l[indent:])
open(sys.argv[2], "w").write("\n".join(body) + "\n")
PY
assert_contains "$(cat "$TMP/guard.sh")" "git apply --index" "extracted the guard step"

# guard <description> <expected exit>: package the working-tree change as the harden job does,
# reset, then run the guard against the patch.
guard() {
  local desc="$1" want="$2"
  mkdir -p "$TMP/handoff"
  git add -A && git diff --cached --binary > "$TMP/handoff/changes.patch" && git reset -q --hard
  assert_exit "$want" "$desc" -- env SKILL=pr-review RUNNER_TEMP="$TMP" bash "$TMP/guard.sh"
  git reset -q --hard
}

S=evals/pr-review
mkdir -p $S/fixtures
echo "diff" > $S/fixtures/new-attack.diff
echo '{"id": "pr-review-x-001"}' > $S/cases/adversarial/pr-review-x-001.json
git mv $S/cases/adversarial/pr-review-conflicting-scope-001.json $S/cases/regression/
python3 -c 'import json; p="evals/pr-review/spec.json"; d=json.load(open(p)); d["version"]="1.0.1"; json.dump(d, open(p,"w"), indent=2)'
echo "- new guidance" >> claude/skills/pr-review/factors/3-security-data-protection.md
guard "allowed: new case and fixture, unchanged promotion, version bump, fixable file edit" 0
assert_contains "$OUT" "ok      M claude/skills/pr-review/factors/3-security-data-protection.md" "fixable file accepted"

echo "x" >> claude/skills/pr-review/SKILL.md
guard "refused: SKILL.md is not in pr-review's fixable_files" 1
assert_contains "$OUT" "REFUSED M claude/skills/pr-review/SKILL.md" "names the refused path"

echo " " >> $S/cases/regression/pr-review-logic-off-by-one-001.json
guard "refused: editing an existing regression case" 1

python3 -c 'import json; p="evals/pr-review/spec.json"; d=json.load(open(p)); d["fixable_files"].append("SKILL.md"); json.dump(d, open(p,"w"), indent=2)'
guard "refused: widening fixable_files in spec.json" 1

git mv $S/cases/adversarial/pr-review-conflicting-scope-001.json $S/cases/regression/
echo " " >> $S/cases/regression/pr-review-conflicting-scope-001.json
guard "refused: promotion that also edits the case" 1

echo "# x" >> scripts/eval.sh
guard "refused: harness change" 1

echo '{}' > evals/onboard-tool/cases/adversarial/onboard-tool-x-001.json
guard "refused: adding cases for a different skill" 1
done_tests
