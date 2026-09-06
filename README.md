# ai-toolkit

Personal library of AI coding-assistant skills, agents, and helper
configs, organized by tool so each one's native format stays intact.

```
claude/     — Claude Code skills (SKILL.md-based)
copilot/    — GitHub Copilot custom instructions / prompt files
grok/       — Grok helper configs
gemini/     — Gemini skill/extension configs
docs/specs/ — Design docs for anything non-trivial built here
docs/plans/ — Implementation plans for anything non-trivial built here
```

## Rules for what goes in this repo

- No personal information, credentials, tokens, internal hostnames, or
  anything that reveals a specific employer's codebase, workflow, or
  business logic. Skills should be generic and reusable across
  projects.
- Before committing a new skill, scan it for anything company- or
  person-specific and generalize it.

## Claude skills

Claude Code loads personal skills from `~/.claude/skills/`, which also
holds other unrelated personal skills belonging to the repo owner (some
with credentials). To avoid exposing those to this repo, skills built
here are symlinked **individually**, never as a whole-directory symlink:

```
~/.claude/skills/pr-review        -> ~/Projects/ai-toolkit/claude/skills/pr-review
~/.claude/skills/pr-review-harden -> ~/Projects/ai-toolkit/claude/skills/pr-review-harden
```

Adding a new skill here means adding one new individual symlink for
it — never symlink `~/.claude/skills` itself.
