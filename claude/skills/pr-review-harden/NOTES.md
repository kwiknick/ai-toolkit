# Path to scheduled runs

`/pr-review-harden` is manually triggered today. Once it's been run a
few times and the escalation/regression behavior looks right, promote
it to a weekly cadence using the `schedule` skill:

1. Invoke the `schedule` skill and create a routine on a weekly cron
   (e.g. Monday 9am) whose action is running `/pr-review-harden`.
2. Have the routine's completion report (or a follow-up step) surface
   the run report's summary somewhere you'll actually see it - e.g.
   post the "N escalated / N plateaued / N drift alarms / N pending
   patches" summary line as the routine's notification text, since
   pending patches still require your manual approval before they
   touch any `pr-review/factors/<slug>.md` file.
3. Do not have the schedule auto-apply pending patches. Keep that
   gate manual indefinitely - see the design spec's rationale for why
   this skill never self-edits `pr-review` content autonomously.

Status: the first live run happened on 2026-09-06 (10/10 catches at
level 1 — see `runs/2026-09-06.md`). The loop's basic shape is
validated; promote to cron once a few more runs (ideally including at
least one real miss, to exercise the regression-corpus and
pending-patch paths) look sane.
