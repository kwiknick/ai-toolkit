# GitHub setup

## Workflows

| Workflow | Trigger | Token | Model calls | What it does |
|---|---|---|---|---|
| `eval-pr.yml` (job **eval-gate**) | PR opened, updated, labeled | `contents: read` | Only if the PR changes a skill | Harness tests, static validation, append-only check on `evals/`, then the regression set on the real model for changed skills. |
| `eval-main.yml` | Push to `main`, manual | `contents: read` | All skills | Regression set for every skill. Results kept as an artifact for 90 days. |
| `harden-scheduled.yml` | Mondays 09:17 UTC, manual (optional `skill`) | `harden`: read. `open-pr`: write | One skill | Runs `/harden-skill` on one skill (rotating by week). A second job checks the changed paths and opens a **draft** PR. Never merges. |

Actions are pinned to commit SHAs and Dependabot keeps them current.
Claude Code is pinned with `CLAUDE_CODE_VERSION` at the top of each
workflow.

"Changed skills" means skills with files changed under
`claude/skills/<name>/` or `evals/<name>/`. A change to the harness
(`tools/aitk/`), the judge prompt, the security policy, or
`aitk.config.json` reruns every skill, because it can change how all of
them are graded.

## Secrets and variables

| Name | Kind | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | secret | All three workflows. For Bedrock, replace it with AWS credentials and `CLAUDE_CODE_USE_BEDROCK=1`. |
| `AITK_PR_TOKEN` | secret | Recommended. A fine-grained token for this repository only, with `contents` and `pull_requests` write. PRs opened with the default `GITHUB_TOKEN` don't trigger workflows, so `eval-gate` wouldn't run on hardening PRs. |
| `AITK_PR_MAX_USD` | variable | Dollar cap for a PR run (default 5). |
| `AITK_MAIN_MAX_USD` | variable | Dollar cap for the post-merge run (default 10). |
| `AITK_HARDEN_SESSION_MAX_USD` | variable | Cap for the hardening session itself (default 5). Each `eval.sh` run inside it has its own cap. |

If you don't create `AITK_PR_TOKEN`, enable Settings > Actions > General >
"Allow GitHub Actions to create and approve pull requests", and push an
empty commit to a hardening PR to start its gate.

## Require the gate

A red check doesn't block a merge by itself. The default branch needs a
ruleset that requires it:

```bash
./scripts/github-protection.sh print                         # the ruleset JSON
./scripts/github-protection.sh apply --repo OWNER/REPO --yes # needs repo admin; changes settings
./scripts/github-protection.sh verify --repo OWNER/REPO      # read-only; exit 1 if anything is missing
```

The ruleset requires:

- the `eval-gate` status check, from GitHub Actions only, with the branch
  up to date;
- a PR with 1 approval, code-owner review, approval of the latest push,
  stale approvals dismissed, and all threads resolved;
- no force pushes and no branch deletion.

**Solo maintainer:** GitHub won't let you approve your own PR. Either add a
bypass for yourself and keep the required check, or add a second reviewer.
Hardening PRs are authored by the bot token, so your approval of those is
a real review.

## Security notes

- **PR code runs with the API key.** The gate uses `pull_request`, not
  `pull_request_target`. Fork PRs get no secrets, and a fork PR that
  changes a skill fails the gate instead of skipping. A branch in this
  repo does get the key, so anyone who can push branches can read it. For
  a personal repo that's you. For a shared repo, put the real-model step
  behind a GitHub environment with required reviewers.
- **The hardening agent never holds write access.** It runs on reviewed
  `main` code with a read-only token. Its changes leave as a patch. The
  `open-pr` job runs no repository code and no model. It applies the
  patch and, using only git and jq, refuses any path outside the allowlist
  before pushing. The allowlist comes from `spec.json` at `HEAD`, not from
  the patch.
- **The label is not the control.** `criteria-change-approved` lets an
  edit to existing eval files through the integrity check. Anyone with
  triage rights can add a label, so the real control is CODEOWNERS review
  of `evals/` in the ruleset.

## Not verified here

These workflows have not run on GitHub yet. Locally verified: the YAML
parses, every script they call is covered by `./scripts/test.sh`, and the
path guard's exact shell is tested in `tests/shell/test_harden_guard.sh`.
That `claude -p "/harden-skill <skill>"` runs the skill headlessly in
Actions still needs a first real run.
