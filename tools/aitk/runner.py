"""Run static validation and eval cases; write results.json, summary.md, and evidence."""

import hashlib
import json
from pathlib import Path

from aitk import assertions, cases as casemod, providers, skills
from aitk.util import git_commit, git_dirty, now_iso, redact

EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2


def build_system(skill, case):
    """Concatenate the skill files a case loads as instructions (globs allowed)."""
    parts = []
    for pattern in case.system_files:
        paths = sorted(skill.path.glob(pattern), key=lambda p: (len(p.name), p.name))
        if not paths:
            raise ValueError(f"system file {pattern!r} not found in {skill.name}")
        for path in paths:
            if skill.path.resolve() not in path.resolve().parents:
                raise ValueError(f"system file {pattern!r} escapes the skill directory")
            parts.append(f"<!-- {path.relative_to(skill.path)} -->\n{path.read_text()}")
    return "\n\n".join(parts)


def _worst(statuses):
    for s in ("error", "fail", "pass"):
        if s in statuses:
            return s
    return "skip"


def run_case(skill, case, provider, ctx, repeat):
    attempts = []
    for _ in range(max(1, repeat)):
        try:
            req = providers.Request(system=build_system(skill, case), prompt=case.prompt(), case=case,
                                    tools=case.data.get("tools"),
                                    permission_mode=case.data.get("permission_mode"))
            resp = provider.complete(req)
        except providers.BudgetExceeded:
            raise
        except (providers.ProviderError, ValueError, OSError) as e:
            attempts.append({"status": "error", "error": redact(str(e))})
            continue
        results = []
        for a in case.assertions:
            try:
                status, msg = assertions.check(a, resp, skill, case, ctx)
            except providers.BudgetExceeded:
                raise
            except providers.ProviderError as e:
                status, msg = "error", f"judge failed: {e}"
            except Exception as e:  # a bad assertion is an error for this case, not a crashed run
                status, msg = "error", f"assertion crashed: {type(e).__name__}: {e}"
            results.append({"type": a["type"], "status": status, "message": redact(msg)})
        attempts.append({"status": _worst({r["status"] for r in results}), "assertions": results,
                         "output": redact(resp.text),
                         "tool_calls": json.loads(redact(json.dumps(resp.tool_calls))),
                         "cost_usd": resp.cost_usd})
    statuses = [a["status"] for a in attempts]
    fails = statuses.count("fail")
    return {
        "id": case.id, "skill": skill.name, "set": case.set, "category": case.category,
        "status": _worst(set(statuses)), "fails": fails, "attempts_run": len(attempts),
        # Reproducible = failed on every attempt. Hardening only acts on reproducible failures.
        "reproducible": fails > 0 and fails == len(attempts),
        "expected_behavior": case.expected_behavior, "attempts": attempts,
    }


def run(skill_names, sets, cfg, out_dir, skills_root=skills.SKILLS_ROOT, evals_root=skills.EVALS_ROOT,
        case_ids=None, static_only=False):
    budget = providers.Budget(cfg["max_model_calls"], cfg["max_usd"])
    policy = skills.load_policy(evals_root)
    provider = judge = None
    judge_prompt = (evals_root / "judge-prompt.md").read_text()
    if not static_only:
        provider = providers.make(cfg["provider"], cfg, budget)
        judge = providers.make(cfg["provider"], cfg, budget, model=cfg.get("judge_model") or cfg.get("model"))
    ctx = {"policy": policy, "judge": judge, "judge_prompt": judge_prompt}

    results = {
        "started": now_iso(), "git_commit": git_commit(), "git_dirty": git_dirty(),
        "provider": provider.name if provider else None, "model": provider.model if provider else None,
        "judge_model": judge.model if judge else None,
        "judge_prompt_sha": hashlib.sha256(judge_prompt.encode()).hexdigest()[:12],
        "sets": list(sets), "static": {}, "cases": [], "error": None,
    }
    try:
        for name in skill_names:
            skill = skills.load(name, skills_root, evals_root)
            issues = skills.validate(skill, policy)
            # Validate every case in every set; run only the requested ones.
            case_list, case_errors = (casemod.load_cases(skill, casemod.SETS, policy["allowed_permission_modes"])
                                      if skill.spec else ([], []))
            case_list = [c for c in case_list if c.set in sets and (not case_ids or c.id in case_ids)]
            issues += [("error", "bad-case", e) for e in case_errors]
            results["static"][name] = {
                "version": skill.spec.get("version"),
                "errors": [f"{c}: {m}" for lvl, c, m in issues if lvl == "error"],
                "warnings": [f"{c}: {m}" for lvl, c, m in issues if lvl == "warning"],
            }
            if static_only or results["static"][name]["errors"]:
                continue  # never spend money on a skill that fails static validation
            for case in case_list:
                if provider.mocked and "mock" not in case.data:
                    results["cases"].append({"id": case.id, "skill": name, "set": case.set,
                                             "category": case.category, "status": "skip",
                                             "skip_reason": "no mock response", "attempts": []})
                    continue
                repeat = case.data.get("repeat", cfg["repeat"])
                results["cases"].append(run_case(skill, case, provider, ctx, repeat))
    except providers.BudgetExceeded as e:
        results["error"] = str(e)
    results["model_calls"] = budget.calls
    results["cost_usd"] = round(budget.usd, 4)
    results["finished"] = now_iso()
    results["summary"] = summarize(results)
    write(results, out_dir)
    return results


def summarize(results):
    per_skill = {name: {"version": st["version"], "static_errors": len(st["errors"]),
                        "pass": 0, "fail": 0, "skip": 0, "error": 0}
                 for name, st in results["static"].items()}
    for c in results["cases"]:
        per_skill[c["skill"]][c["status"]] += 1
    for s in per_skill.values():
        s["status"] = "FAIL" if (s["static_errors"] or s["fail"]) else ("ERROR" if s["error"] else "PASS")
    return per_skill


def exit_code(results):
    s = results["summary"].values()
    if any(x["status"] == "FAIL" for x in s):
        return EXIT_FAIL
    if results["error"] or any(x["status"] == "ERROR" for x in s):
        return EXIT_ERROR
    return EXIT_PASS


def write(results, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    (out_dir / "summary.md").write_text(markdown(results))
    for c in results["cases"]:
        if c.get("attempts"):
            ev = out_dir / "evidence"
            ev.mkdir(exist_ok=True)
            parts = [f"# Evidence: {c['id']} ({c['status']}, {c['fails']}/{c['attempts_run']} attempts failed)\n",
                     f"provider={results['provider']} model={results['model']}\n"]
            for i, a in enumerate(c["attempts"], 1):
                parts.append(f"## Attempt {i}: {a['status']}\n")
                parts += [f"- `{r['type']}` {r['status']}: {r['message']}" for r in a.get("assertions", [])]
                parts += [f"\n### Output\n\n{a.get('output') or a.get('error', '')}\n",
                          f"### Tool calls\n\n```json\n{json.dumps(a.get('tool_calls', []), indent=2)}\n```\n"]
            (ev / f"{c['id']}.md").write_text("\n".join(parts))


def _fence(text, limit=800):
    text = (text or "").strip()
    if len(text) > limit:
        text = text[:limit] + "\n... [truncated, see evidence/]"
    return "```text\n" + text.replace("```", "`\u200b``")  # zero-width space keeps the fence from closing early + "\n```"


def markdown(results):
    lines = ["# Eval results", ""]
    if results["provider"] == "mock":
        lines += ["> **MOCK PROVIDER.** Canned responses. This tests the harness, not a skill.", ""]
    elif results["provider"]:
        same = results["judge_model"] == results["model"]
        lines += [f"> Model `{results['model']}`, judge `{results['judge_model']}`"
                  f"{' (same model: rubric scores are self-graded)' if same else ''} "
                  f"(prompt {results['judge_prompt_sha']}), {results['model_calls']} calls, "
                  f"${results['cost_usd']:.2f}.", ""]
    else:
        lines += ["> Static validation only. No model calls.", ""]
    lines += [f"Commit `{(results.get('git_commit') or 'n/a')[:12]}`"
              f"{' (dirty tree)' if results.get('git_dirty') else ''}, sets: {', '.join(results['sets'])}", ""]
    if results.get("error"):
        lines += [f"**Run stopped:** {results['error']}", ""]
    lines += ["| Skill | Version | Status | Pass | Fail | Skip | Error | Static errors |",
              "|---|---|---|---|---|---|---|---|"]
    for name, s in results["summary"].items():
        lines.append(f"| {name} | {s['version']} | **{s['status']}** | {s['pass']} | {s['fail']} | "
                     f"{s['skip']} | {s['error']} | {s['static_errors']} |")
    lines.append("")
    for name, st in results["static"].items():
        if st["errors"] or st["warnings"]:
            lines.append(f"### Static validation: {name}")
            lines += [f"- ERROR {e}" for e in st["errors"]] + [f"- warning {w}" for w in st["warnings"]]
            lines.append("")
    if results["cases"]:
        lines += ["### Cases", "", "| Case | Set | Category | Status |", "|---|---|---|---|"]
        for c in results["cases"]:
            note = f" ({c['skip_reason']})" if c.get("skip_reason") else ""
            if c.get("attempts_run", 0) > 1:
                note += f" ({c['fails']}/{c['attempts_run']} failed)"
            last = c["attempts"][-1] if c["attempts"] else {}
            skipped = sum(a["status"] == "skip" for a in last.get("assertions", []))
            if skipped:
                note += f" ({skipped} assertion(s) skipped)"
            lines.append(f"| {c['id']} | {c['set']} | {c['category']} | {c['status']}{note} |")
        lines.append("")
    for c in results["cases"]:
        if c["status"] not in ("fail", "error"):
            continue
        last = next((a for a in reversed(c["attempts"]) if a["status"] == c["status"]), c["attempts"][-1])
        lines += [f"### {c['status'].upper()}: {c['id']}", "", f"Expected: {c['expected_behavior']}", ""]
        for a in last.get("assertions", []):
            if a["status"] != "pass":
                lines.append(f"- `{a['type']}` {a['status']}: {a['message']}")
        if last.get("error"):
            lines.append(f"- error: {last['error']}")
        lines += ["", "Output excerpt:", "", _fence(last.get("output")), ""]
    return "\n".join(lines)
