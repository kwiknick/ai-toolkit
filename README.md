# ai-toolkit

Personal library of AI coding-assistant skills, agents, and helper
configs, organized by tool so each one's native format stays intact.

```
claude/     — Claude Code skills (SKILL.md-based)
copilot/    — GitHub Copilot custom instructions / prompt files (placeholder, empty)
grok/       — Grok helper configs (placeholder, empty)
gemini/     — Gemini skill/extension configs (placeholder, empty)
docs/specs/ — Design docs for anything non-trivial built here
docs/plans/ — Implementation plans for anything non-trivial built here
```

## What's here today

**`claude/skills/pr-review`** — reviews a PR diff against a 10-factor
engineering rubric (architecture, correctness, security, performance,
error handling, tests, readability, concurrency, docs, standards). It's
a fan-out orchestrator: it dispatches one focused subagent per factor
(each following the rules in `shared-review-discipline.md` — verify
claims against the diff instead of trusting the description, tag every
finding with a severity and a confidence level, flag new dependencies,
run a self-adversarial check before finalizing) and aggregates their
findings into one report.

**`claude/skills/pr-review-harden`** — a companion self-hardening loop.
Invoke it as `/pr-review-harden` to red-team `pr-review`: it re-runs a
locked regression corpus (cases it has missed before, which must never
be missed again), then throws one new escalating adversarial case per
review factor at it, bumping that factor's difficulty after repeated
catches (capped at level 3, to avoid over-fitting the rubric to
unrealistic tricks) and proposing — never auto-applying — a fix to the
missed factor's own file when something gets through. See
`claude/skills/pr-review-harden/NOTES.md` for current status and the
path to running this on a schedule.

Full design rationale lives in
[`docs/specs/2026-09-06-pr-review-harden-design.md`](docs/specs/2026-09-06-pr-review-harden-design.md);
the implementation plan (useful if you want to see how it was built,
task by task) is in
[`docs/plans/2026-09-06-pr-review-harden.md`](docs/plans/2026-09-06-pr-review-harden.md).

`copilot/`, `grok/`, and `gemini/` are placeholders for the same kind
of thing in other tools' native formats — nothing's in them yet.

## Getting started

Claude Code loads personal skills from `~/.claude/skills/`. That
directory is typically shared across all your projects and may already
hold other, unrelated skills of your own — so skills from this repo
are symlinked in **individually**, never as a whole-directory symlink
(that would expose everything else in `~/.claude/skills/` to this
repo's git history).

```bash
git clone <this-repo-url> ~/Projects/ai-toolkit   # or wherever you keep projects
ln -s ~/Projects/ai-toolkit/claude/skills/pr-review        ~/.claude/skills/pr-review
ln -s ~/Projects/ai-toolkit/claude/skills/pr-review-harden ~/.claude/skills/pr-review-harden
```

Start a new Claude Code session (skills are discovered at session
start) and both are available:

```
/pr-review           # review a PR/diff against the 10-factor rubric
/pr-review-harden     # run the self-hardening red-team loop
```

Adding a new skill to this repo later means adding one new individual
symlink for it — never symlink `~/.claude/skills` itself.

## License

MIT — see [LICENSE](LICENSE).

## Rules for what goes in this repo

- No personal information, credentials, tokens, internal hostnames, or
  anything that reveals a specific employer's codebase, workflow, or
  business logic. Skills should be generic and reusable across
  projects.
- Before committing a new skill, scan it for anything company- or
  person-specific and generalize it.
