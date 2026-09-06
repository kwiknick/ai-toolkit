# Real seeds: 2-logic-correctness

Drop anonymized snippets from real past bad PRs/incidents here, one per
file, named descriptively (e.g. `unbounded-retry-loop.md`):

```markdown
---
factor: 2-logic-correctness
added: YYYY-MM-DD
used: false
---

## Snippet
<anonymized code — no company names, internal URLs, real identifiers>

## What made this a real problem
<1-2 sentences of context>
```

**Before committing anything here: scrub it.** No company-specific
names, internal hostnames, credentials, or personally identifying
details — see the repo README's rules.

`/pr-review-harden`'s escalation probe (Phase 2) draws from here about
25% of the time when an unused (`used: false`) seed exists for the
factor being probed; otherwise it generates a synthetic case. Once a
seed is used, its `used` field flips to `true` so it isn't recycled
verbatim next time (delete it, or add a fresh one, once it's actually
answered in the corpus).
