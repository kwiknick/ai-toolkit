# Regression cases: 4-performance-scale

Each locked case lives in its own file here, named `<case-id>.md`:

```markdown
---
id: <case-id>
factor: 4-performance-scale
level: <1-3>
source: synthetic | real-seed
added: YYYY-MM-DD
status: active
---

## Adversarial snippet
<code block reproducing the missed bug>

## Expected finding
<what the factor subagent must flag, and why>

## History
- YYYY-MM-DD: missed, patch proposed and applied to factors/4-performance-scale.md
- YYYY-MM-DD: caught in regression sweep
```

Cases here are locked: every `/pr-review-harden` run's regression sweep
(Phase 1) re-tests every file in this directory against a fresh
subagent given `shared-review-discipline.md` plus
`pr-review/factors/4-performance-scale.md` — the same isolated shape a real factor
subagent runs in. A case that stops being caught is a drift alarm, not
a new escalation miss.
