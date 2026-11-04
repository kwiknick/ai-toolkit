# How it works

The goal is to change a skill with the same confidence as changing code. A
skill's behavior can't be read off its text; it only shows up when a model
runs it. So every skill carries cases that run it against the real model,
merges require those cases to pass, and new attacks are added on a schedule
so the cases keep getting harder. A model writes attacks and drafts fixes,
but deterministic checks decide whether a fix worked and a person decides
whether it merges.

## The pieces

| Piece | Where | Job |
|---|---|---|
| Skill | `claude/skills/<name>/` | Instructions Claude Code loads. `allowed-tools` in the frontmatter limits what it can do without asking. |
| Spec | `evals/<name>/spec.json` | `version`, `expected_behavior`, attack `categories`, `output_contracts`, `fixable_files`. |
| Cases | `evals/<name>/cases/{regression,adversarial}/*.json` | One input and the checks its output must pass. |
| Fixtures | `evals/<name>/fixtures/` | Inputs: a diff to review, or a small repository the skill works in. |
| Harness | `tools/aitk/`, `scripts/eval.sh` | Runs cases against the model and grades them. |
| Hardening skill | `claude/skills/harden-skill/` | Writes attacks, drafts fixes, writes the PR description. |
| Workflows | `.github/workflows/` | PR gate, post-merge run, weekly hardening. |

Specs and cases sit outside the skill folder on purpose. The model under
test gets only the skill files, so it can't read its own grading criteria.

## Running a case

For each case, `eval.sh`:

1. Builds the system prompt from the skill files the case lists
   (`system_files`, default `SKILL.md`). A pr-review case can load one
   factor file and test it in isolation.
2. Creates a temporary sandbox directory. If the case has a `workspace`
   fixture, copies it in and makes it a git repo.
3. Runs `claude -p` there. The skill is appended to the system prompt, and
   the run has only the tools the case lists (none by default) and a
   per-call dollar cap. The run is isolated from your MCP servers, hooks,
   and user settings (`--strict-mcp-config --setting-sources project`).
4. Records the final answer and every tool call. Secrets are redacted.
5. Runs the case's assertions on the result.

A case passes when every assertion passes on every attempt (`--repeat N`).

## Assertions

| Type | Checks |
|---|---|
| `regex`, `not_regex` | A pattern is present or absent. Case-insensitive by default. |
| `contract` | The output has the sections and patterns named in the spec's `output_contracts`. |
| `severity_at_least`, `severity_at_most` | A finding matching `near` carries an explicit severity tag at or above (or below) a level. |
| `max_matches` | A pattern appears at most N times, for example "no Dockerfile in a minimal plan". |
| `only_reference_files` | The output names no files that aren't in the input (invented findings). |
| `no_tool_calls` | The model did not call these tools, for example `Write` before approval. |
| `no_dangerous_actions` | No tool call or suggested shell block matches the security policy (`curl \| sh`, reading `~/.aws/credentials`, force push, and so on). |
| `rubric` | A judge model scores criteria from 1 to 5 using `evals/judge-prompt.md`. Default pass is 4. |

Deterministic checks come first because they are free, fast, and give the
same answer every time. The rubric covers what a pattern can't, such as
"identifies the comment as an attempt to suppress the review".

The judge runs on a different model than the skill (`judge_model` in
`aitk.config.json`). This hedges against a model grading its own style.
The judge prompt is a versioned file under `evals/`, so it can't change
without review, and every result records its hash.

## Static validation

`eval.sh --static` makes no model calls. For every skill it checks:

- Frontmatter: name matches the folder, description present and under
  1024 characters, no unscoped `Bash` in `allowed-tools`.
- The spec exists, has the required fields, and its `fixable_files`
  globs match real files.
- At least one regression case, and every case in every set is valid.
- No broken file references and no committed secrets in skill files.

## Two case sets

- **regression**: behavior that must keep working. Gates merges.
- **adversarial**: attacks and known open weaknesses. Reported, never
  gating, so an unfixed weakness in one skill doesn't block unrelated PRs.

A weakness becomes a regression case when a fix makes it pass: the case
moves, unchanged, from `adversarial/` to `regression/`.

There's no hidden holdout set. In a public repo, anything hidden is only
hidden from the model, not from people, so human review of each hardening
PR is the guard against fixes written to the test.

## Hardening

`/harden-skill <skill>` is a skill, not a script. Writing realistic attacks
and diagnosing failures is creative work a model is good at. Deciding
whether a fix worked is not, so that part belongs to `eval.sh`.

1. **Drift check.** Run the regression set. If it fails, stop.
2. **Attack.** Write N new cases (default 3) for the categories with the
   fewest cases. Each gets a rubric assertion plus the deterministic
   safety checks that apply.
3. **Confirm.** Run each new case twice. 2 of 2 failures is a confirmed
   weakness; 1 of 2 is reported as flaky and left alone.
4. **Fix.** For each confirmed weakness, make the smallest edit in a
   `fixable_files` file. Rerun the case twice and the whole regression set.
   Accept only if all pass, then promote the case and bump the spec's
   patch version. Otherwise undo the edit, with at most two attempts.
5. **Report.** Write `.aitk/harden/pr-body.md`: the cases, before and
   after results, the root-cause hypothesis, the diff, the cost, and a
   checklist for the reviewer.

## Guardrails

| Risk | Control |
|---|---|
| A change weakens or deletes a test to make it pass | `aitk integrity` in the PR gate: existing files under `evals/` are append-only. The only exceptions are an unchanged promotion and a `version` bump. Override needs the `criteria-change-approved` label, and CODEOWNERS requires code-owner review of `evals/`. |
| The hardening agent edits more than it should | It runs with a read-only token. A separate job with no model and no repo code applies its patch and refuses any path outside: new files under `evals/<skill>/`, unchanged promotions, a version bump, and edits to that skill's `fixable_files`. Tested in `tests/shell/test_harden_guard.sh`. |
| Self-grading | A separate judge model with a fixed prompt, deterministic checks first, and a human merges. |
| A flaky failure triggers a bad fix | Only 2 of 2 failures get a fix. |
| A skill runs something dangerous | `no_dangerous_actions` on every tool call and suggested shell block; static rejection of unscoped `Bash`. |
| Runaway cost | A per-run dollar cap and call cap (exit 2 when hit), a per-call `--max-budget-usd`, timeouts, and the PR gate runs only changed skills. |
| Secrets in results | Values of known secret env vars and common token patterns are redacted from results and evidence. |

## Configuration

`aitk.config.json`, overridden by environment variables, overridden by flags.

| Key | Env | Default |
|---|---|---|
| `model` | `AITK_MODEL` | `opus`, a `claude --model` value |
| `judge_model` | `AITK_JUDGE_MODEL` | `sonnet` |
| `max_usd` | `AITK_MAX_USD` | 5.0 per run |
| `max_model_calls` | `AITK_MAX_MODEL_CALLS` | 40 per run |
| `call_max_usd` | | 1.0 per `claude -p` call |
| `call_timeout_s` | `AITK_CALL_TIMEOUT_S` | 300 |

To run on Amazon Bedrock instead of the Anthropic API, configure Claude
Code for Bedrock (`CLAUDE_CODE_USE_BEDROCK=1` plus AWS credentials). The
harness only calls `claude`.

The `mock` provider returns canned answers from a case's `mock` block.
Only the harness's own tests use it (`./scripts/test.sh`), and `eval.sh`
refuses it, so a real skill is never "passed" by canned answers.

## Results

Each run writes `.aitk/results/<run-id>/`:

- `summary.md`: a pass/fail table per skill and per case, plus the
  assertion messages and an output excerpt for each failure. CI adds it to
  the job summary.
- `results.json`: everything, including every attempt, tool calls, cost,
  model, judge model, judge prompt hash, and commit.
- `evidence/<case>.md`: full output and tool calls for each attempt.
