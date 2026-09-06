# ai-toolkit

Personal library of AI coding-assistant skills, agents, and helper
configs, organized by tool so each one's native format stays intact.

```
claude/     — Claude Code skills (SKILL.md-based)
copilot/    — GitHub Copilot custom instructions / prompt files
grok/       — Grok helper configs
gemini/     — Gemini skill/extension configs
docs/specs/ — Design docs for anything non-trivial built here
```

## Rules for what goes in this repo

- No personal information, credentials, tokens, internal hostnames, or
  anything that reveals a specific employer's codebase, workflow, or
  business logic. Skills should be generic and reusable across
  projects.
- Before committing a new skill, scan it for anything company- or
  person-specific and generalize it.

## Claude skills

`claude/skills/` is symlinked from `~/skills` so editing a skill here
*is* editing the live skill Claude Code loads — this repo is the
single source of truth, git tracks every revision.
