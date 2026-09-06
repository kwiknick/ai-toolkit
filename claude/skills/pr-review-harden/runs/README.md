# Run reports

One file per `/pr-review-harden` invocation, named `YYYY-MM-DD.md`
(append `-2`, `-3`, ... if run more than once in a day). Each report
contains:

1. **Regression sweep results** — a table of every locked case
   (factor, case id, level, pass/fail). Any fail is a drift alarm,
   called out at the top of the report.
2. **Escalation probe results** — a table of the one new case
   generated per non-plateaued factor (factor, level, source
   synthetic/real-seed, catch/miss).
3. **Pending factor-file patches** — for any miss, the proposed patch
   text (a single bullet addition under the relevant factor's
   `## Check for` list in `pr-review/factors/<slug>.md`) awaiting
   human approval. Never pre-applied. `pr-review/SKILL.md` and
   `pr-review/shared-review-discipline.md` are never patched by this
   loop.
4. **Consolidation flag** — if any `pr-review/factors/<slug>.md` file
   has grown past ~15 bullet points under `## Check for`, note it here
   as a signal to run a manual consolidation pass.
