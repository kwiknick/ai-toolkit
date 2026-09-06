---
name: pr-review-harden
description: Run the self-hardening red-team loop against the pr-review skill - a regression sweep over locked cases plus one escalating adversarial probe per non-plateaued factor. Use when the user says "harden pr review", "red-team the reviewer", or invokes /pr-review-harden.
---

# PR Review Hardening Loop

This skill tests and incrementally strengthens the companion
`pr-review` skill's per-factor content
(`~/.claude/skills/pr-review/factors/<slug>.md`). It never edits that
file itself, and never touches `pr-review/SKILL.md` or
`pr-review/shared-review-discipline.md` at all — every fix it finds is
proposed to the user as a patch to the relevant factor file and only
applied on explicit approval.

All paths below are relative to this skill's own directory,
`~/.claude/skills/pr-review-harden/` (a symlink into the `ai-toolkit`
repo — read and write through it normally), except references to
`pr-review/...` which are its sibling skill directory,
`~/.claude/skills/pr-review/`.

## Phase 1: Regression sweep

1. For every `regression-cases/<slug>/<case-id>.md` file that exists:
   - Parse its frontmatter and the "Adversarial snippet" / "Expected
     finding" sections.
   - Dispatch a fresh subagent whose *only* context is
     `pr-review/shared-review-discipline.md` plus
     `pr-review/factors/<slug>.md` (that case's own factor only),
     given the adversarial snippet framed as a PR diff to review — the
     subagent must not know this is a test.
   - Compare the subagent's output against the case's "Expected
     finding" — did it flag the same underlying issue (semantic match,
     not exact wording)?
   - Record pass/fail. Do **not** touch `state/factor-difficulty.json`
     based on this phase — it is a drift check, not an escalation
     signal.
2. Any fail here is a **drift alarm**: something in
   `pr-review/factors/<slug>.md` (or, if it affects everything, the
   shared discipline file) regressed. Surface it prominently at the
   top of the run report.

If `regression-cases/` has no case files yet (first run), Phase 1
trivially passes with zero cases swept — note that in the report rather
than skipping the section.

## Phase 2: Escalation probe

1. Read `state/factor-difficulty.json`.
2. For each factor **not** marked `"status": "plateaued"`:
   a. Look for an unused real seed: any file in
      `real-seeds/<slug>/` with `used: false` in its frontmatter.
      With that seed present, use it about 1 time in 4 (roll a random
      choice); otherwise, and always when no unused seed exists,
      generate a **synthetic** adversarial case yourself, targeting
      that factor specifically, at the difficulty level named in the
      table below for the factor's current `level`.
   b. **Difficulty guidance** (never exceed level 3 — the ceiling is
      deliberate, see the design spec's anti-overfitting rationale):
      - Level 1: an obvious mistake a junior reviewer would catch.
      - Level 2: requires actually reading the diff carefully.
      - Level 3: a plausible mistake a competent senior engineer could
        make under time pressure — realistic, not contrived.
   c. Dispatch a fresh subagent scoped exactly like Phase 1 (shared
      discipline + that factor's file only) to review the
      generated/seed case, same "must not know it's a test" isolation.
   d. Score catch vs. miss against what the case was actually designed
      to trigger for that factor.
   e. Update state:
      - **Catch:** `consecutive_catches += 1`, `consecutive_misses = 0`.
        If `consecutive_catches >= escalate_after` (3):
        - if `level < ceiling` (3): `level += 1`, reset both counters.
        - else: set `status = "plateaued"`.
      - **Miss:** write the case permanently to
        `regression-cases/<slug>/<new-case-id>.md` (status: active,
        source: synthetic or real-seed, level: the level it was tested
        at) using the format documented in that directory's README.
        Set `status = "needs_attention"`. Do **not** change `level`.
        Draft one targeted bullet to add under that factor's
        `## Check for` list in `pr-review/factors/<slug>.md`, phrased
        in the same style as the existing bullets, and stage it as a
        "pending patch" for the run report — do not apply it, and do
        not touch `SKILL.md` or `shared-review-discipline.md`.
   f. If a real seed was used, flip its `used` field to `true`.
   g. Set `last_run` to today's date (YYYY-MM-DD) for every factor
      touched this run, whether or not it changed state.
3. Write `state/factor-difficulty.json` back with all updates.

## Reporting

Write `runs/<YYYY-MM-DD>.md` following the format in `runs/README.md`:
regression sweep table, escalation probe table, pending patches (full
diff-style text ready to paste into the relevant
`pr-review/factors/<slug>.md`), and a consolidation flag if any factor
file has grown past ~15 bullets under `## Check for`.

End by telling the user, in the chat, how many factors escalated,
how many plateaued, whether there were any drift alarms, and listing
each pending patch for their explicit yes/no before touching any
`pr-review/factors/<slug>.md` file.
