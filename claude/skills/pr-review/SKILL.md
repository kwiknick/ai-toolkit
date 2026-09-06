---
name: pr-review
description: Review a pull request diff against a 10-factor engineering rubric covering architecture, correctness, security, performance, error handling, tests, readability, concurrency, docs, and standards. Use when asked to review a PR, diff, or code change for quality, or when the user says "review this PR", "code review", or invokes /pr-review.
---

# PR Review Skill

You are orchestrating a review of the provided PR diff (and its
description/context) across 10 factors. This skill's own directory is
`~/.claude/skills/pr-review/` (a symlink into the `ai-toolkit` repo) —
read `shared-review-discipline.md` and the files under `factors/` from
there.

## Steps

1. Read `shared-review-discipline.md` in full.
2. For each of the 10 files under `factors/`, dispatch one subagent in
   parallel. Give each subagent:
   - The PR diff and its description/context, verbatim.
   - `shared-review-discipline.md`, verbatim.
   - That one `factors/<slug>.md` file, verbatim — this subagent
     reviews *only* this factor, and should not attempt the other 9.
   - Instructions to return: any findings for its factor (file/line,
     issue, suggested fix, Severity: Critical/High/Medium/Low, and
     Confidence: CONFIRMED/SUSPECTED per shared discipline rule 4), or
     an explicit statement of what was checked if no issue was found
     (shared discipline rule 2).
3. Once all 10 subagents return, aggregate:
   - Assemble a **Summary** (2-3 sentences: impact, complexity,
     readiness — Approved / Approve with minor fixes / Needs changes —
     plus a one-line severity count, e.g. "1 Critical, 2 High, 3
     Medium, 1 Low").
   - Then a **Findings by Severity** table across all factors, ordered
     Critical → High → Medium → Low, each row: severity, factor,
     file/line, one-line issue.
   - Then all 10 factor sections, in slug order, each titled with the
     factor's `title` from its frontmatter, each finding showing its
     Severity and Confidence tags.
   - Deduplicate: if two subagents flagged the same underlying issue
     (e.g. a new dependency flagged by both the assigned factor and
     Security per shared discipline rule 3), keep it once, filed under
     the more specific factor, and note the cross-reference.
   - Resolve any direct contradictions between subagents by re-reading
     the disputed lines yourself before finalizing.
4. Present the aggregated review. Tone: polite, constructive, critique
   the code not the author; praise genuinely elegant solutions.
