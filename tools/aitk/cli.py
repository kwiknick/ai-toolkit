"""Command-line entry point: python3 -m aitk <command> (see scripts/*.sh wrappers).

Exit codes: 0 pass, 1 eval or integrity failure, 2 error (config, CLI, budget, crash).
"""

import argparse
import json
import re
import sys
from pathlib import Path

from aitk import cases as casemod, integrity, runner, scaffold, skills
from aitk.util import REPO_ROOT, ConfigError, git, load_config, new_run_id

# Changes here can change how every skill is graded, so they re-run every skill.
GLOBAL_PATHS = re.compile(r"^(tools/aitk/|scripts/(aitk|eval\.sh)$|evals/[^/]+\.(json|md)$|aitk\.config\.json$)")
SKILL_PATH = re.compile(r"^(?:claude/skills|evals)/([a-z0-9-]+)/")


def changed_skills(base):
    """Skills whose files (or shared grading files) changed between base and the working tree."""
    paths = git("diff", "--name-only", base).splitlines()
    paths += git("ls-files", "--others", "--exclude-standard").splitlines()
    all_skills = skills.discover()
    if any(GLOBAL_PATHS.match(p) for p in paths):
        return all_skills
    touched = {m.group(1) for p in paths if (m := SKILL_PATH.match(p))}
    return [s for s in all_skills if s in touched]


def cmd_eval(args):
    cfg = load_config({"model": args.model, "judge_model": args.judge_model,
                       "max_model_calls": args.max_calls, "max_usd": args.max_usd, "repeat": args.repeat})
    if cfg["provider"] != "claude-code":
        raise ConfigError(f"provider {cfg['provider']!r}: real skills are evaluated only with claude-code "
                          "(the mock provider exists for the harness's own tests)")
    known = skills.discover()
    if args.changed_since:
        names = changed_skills(args.changed_since)
        print(f"skills changed since {args.changed_since}: {', '.join(names) or 'none'}", file=sys.stderr)
    else:
        names = args.skill or known
    unknown = [n for n in names if n not in known]
    if unknown:
        raise ConfigError(f"unknown skill(s): {unknown}")
    out = Path(args.out) if args.out else REPO_ROOT / cfg["results_dir"] / new_run_id()
    res = runner.run(names, args.set or ["regression"], cfg, out, case_ids=args.case, static_only=args.static)
    if not args.quiet:
        print((out / "summary.md").read_text())
    print(f"results: {out / 'results.json'}\nsummary: {out / 'summary.md'}", file=sys.stderr)
    return runner.exit_code(res)


def cmd_integrity(args):
    violations, notes = integrity.check(args.base)
    for n in notes:
        print(f"ok: {n}")
    for v in violations:
        print(f"{'APPROVED' if args.allow_criteria_change else 'VIOLATION'}: {v}")
    if violations and not args.allow_criteria_change:
        print("Existing eval files are append-only. If this change is intended, get code-owner "
              "review and add the 'criteria-change-approved' label.")
        return runner.EXIT_FAIL
    print(f"integrity OK vs {args.base}")
    return runner.EXIT_PASS


def cmd_new_skill(args):
    for p in scaffold.scaffold(args.name, args.description):
        print(f"created {p.relative_to(REPO_ROOT)}")
    print(f"\nNext: edit the SKILL.md and the example case, then ./scripts/eval.sh --skill {args.name}")
    return runner.EXIT_PASS


def cmd_list(args):
    for name in skills.discover():
        s = skills.load(name)
        counts = {k: len(list((s.evals_dir / "cases" / k).glob("*.json"))) for k in casemod.SETS}
        print(f"{name:20} v{s.spec.get('version', '?'):8} regression={counts['regression']} "
              f"adversarial={counts['adversarial']}")
    return runner.EXIT_PASS


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aitk", description="ai-toolkit skill evals")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("eval", help="static validation plus eval cases")
    e.add_argument("--skill", action="append", help="skill name (repeatable; default: all)")
    e.add_argument("--changed-since", metavar="REF", help="only skills changed since this git ref")
    e.add_argument("--set", action="append", choices=casemod.SETS, help="case set (default: regression)")
    e.add_argument("--case", action="append", help="case id (repeatable)")
    e.add_argument("--static", action="store_true", help="static validation only, no model calls")
    e.add_argument("--model", help="model for the skill under test (claude --model value)")
    e.add_argument("--judge-model", help="model for rubric grading")
    e.add_argument("--repeat", type=int, help="attempts per case")
    e.add_argument("--max-calls", type=int, help="model-call budget for the run")
    e.add_argument("--max-usd", type=float, help="dollar budget for the run")
    e.add_argument("--out", help="results directory")
    e.add_argument("--quiet", action="store_true")
    e.set_defaults(func=cmd_eval)

    i = sub.add_parser("integrity", help="check that existing eval files were only added to")
    i.add_argument("--base", required=True)
    i.add_argument("--allow-criteria-change", action="store_true")
    i.set_defaults(func=cmd_integrity)

    n = sub.add_parser("new-skill", help="scaffold a skill with its eval spec and an example case")
    n.add_argument("name")
    n.add_argument("--description", required=True)
    n.set_defaults(func=cmd_new_skill)

    sub.add_parser("list", help="list skills and case counts").set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
    except (json.JSONDecodeError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
    except Exception as e:  # never let a crash look like "eval failed" (exit 1)
        import traceback
        traceback.print_exc()
        print(f"internal error: {e}", file=sys.stderr)
    return runner.EXIT_ERROR
