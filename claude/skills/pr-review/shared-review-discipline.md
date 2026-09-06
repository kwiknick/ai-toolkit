# Shared Review Discipline

Every factor subagent reviewing a PR — whether as part of a real
`/pr-review` invocation or as part of the `pr-review-harden` hardening
loop testing a single factor in isolation — follows these rules in
addition to its own factor-specific focus:

1. **Don't trust the PR description.** Verify claims (e.g. "tests
   added", "backwards compatible") against the actual diff. A
   confident, well-written description is not evidence the code does
   what it says.
2. **No silent skips.** If you find no issue for your factor, state
   what you specifically checked and ruled out — never leave it blank
   or default to "looks fine" without saying what "fine" was checked
   against.
3. **New dependency = automatic flag.** Any new external
   package/import introduced in the diff gets a mandatory callout,
   filed under Security (3-security-data-protection) regardless of
   which factor you were assigned, even if it looks fine — provenance
   must be explicitly considered, never assumed.
4. **Confidence and severity tagging.** Tag every finding CONFIRMED
   (verified directly against the diff) or SUSPECTED (plausible, but
   you couldn't fully verify it from the diff alone), and give it a
   severity: **Critical** (data loss, security breach, outage-causing),
   **High** (likely user-facing bug or significant risk), **Medium**
   (real but contained issue), or **Low** (style/maintainability nit).
   Severity reflects impact if shipped — not your confidence, and not
   diff size (rule 6).
5. **Adversarial self-check.** After drafting your findings, ask
   yourself: "what would someone trying to sneak something past me
   look for here that I haven't mentioned?" Add anything that surfaces
   before finalizing.
6. **Severity isn't proportional to diff size.** A five-line diff can
   still contain a serious issue. Never downgrade severity just
   because the change is small.
