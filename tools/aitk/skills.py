"""Skill discovery and static validation.

A skill is `claude/skills/<name>/SKILL.md`. Its eval spec lives outside the skill folder,
at `evals/<name>/spec.json`, so the model under test never sees its own grading criteria.
"""

import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from aitk.util import REPO_ROOT, SECRET_PATTERNS, parse_frontmatter

SKILLS_ROOT = REPO_ROOT / "claude" / "skills"
EVALS_ROOT = REPO_ROOT / "evals"

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
# Frontmatter keys documented for Claude Code skills. Others only warn.
KNOWN_FRONTMATTER = {
    "name", "description", "allowed-tools", "argument-hint", "model",
    "disable-model-invocation", "user-invocable", "license", "metadata",
}
SPEC_FIELDS = {"version": str, "expected_behavior": list, "categories": list,
               "output_contracts": dict, "fixable_files": list}
# Backtick-quoted relative paths (must contain a '/'; bare names are usually examples).
REF_RE = re.compile(r"`([A-Za-z0-9_.][A-Za-z0-9_.-]*/[A-Za-z0-9_./-]*\.(?:md|json|sh|py))`")
LINK_RE = re.compile(r"\]\(([^)#\s]+)\)")


@dataclass
class Skill:
    name: str
    path: Path
    evals_dir: Path
    frontmatter: dict
    spec: dict
    issues: list = field(default_factory=list)

    def contract(self, name):
        return (self.spec.get("output_contracts") or {}).get(name)


def load_policy(evals_root=EVALS_ROOT):
    return json.loads((evals_root / "security-policy.json").read_text())


def discover(skills_root=SKILLS_ROOT):
    return sorted(p.parent.name for p in skills_root.glob("*/SKILL.md"))


def load(name, skills_root=SKILLS_ROOT, evals_root=EVALS_ROOT):
    path, evals_dir = skills_root / name, evals_root / name
    issues, fm, spec = [], {}, {}
    try:
        fm, _ = parse_frontmatter((path / "SKILL.md").read_text())
    except FileNotFoundError:
        issues.append(("error", "missing-skill-md", f"{path / 'SKILL.md'} not found"))
    except ValueError as e:
        issues.append(("error", "bad-frontmatter", str(e)))
    try:
        spec = json.loads((evals_dir / "spec.json").read_text())
    except FileNotFoundError:
        issues.append(("error", "missing-spec", f"evals/{name}/spec.json not found (every skill needs evals)"))
    except json.JSONDecodeError as e:
        issues.append(("error", "bad-spec", f"spec.json: {e}"))
    return Skill(name, path, evals_dir, fm, spec, issues)


def _resolve_ref(ref, skill):
    return any((root / ref).exists() for root in (skill.path, skill.path.parent, REPO_ROOT))


def validate(skill, policy):
    """Return a list of (level, code, message). Level is 'error' or 'warning'."""
    issues = list(skill.issues)
    fm, spec = skill.frontmatter, skill.spec

    if fm:
        if fm.get("name") != skill.name:
            issues.append(("error", "name-mismatch",
                           f"frontmatter name {fm.get('name')!r} != directory {skill.name!r}"))
        if not NAME_RE.match(skill.name):
            issues.append(("error", "bad-name", "name must be lowercase letters, digits, hyphens (<=64)"))
        desc = fm.get("description", "")
        if not desc:
            issues.append(("error", "missing-description", "frontmatter description is required"))
        elif len(desc) > 1024:
            issues.append(("error", "description-too-long", f"{len(desc)} chars > 1024"))
        for key in fm:
            if key not in KNOWN_FRONTMATTER:
                issues.append(("warning", "unknown-frontmatter", f"unrecognized frontmatter key {key!r}"))
        for tool in re.split(r",\s*|\s+(?![^(]*\))", fm.get("allowed-tools", "").strip()):
            if tool and tool in policy["forbidden_allowed_tools"]:
                issues.append(("error", "unsafe-allowed-tools",
                               f"allowed-tools grants unscoped {tool!r}; scope it, e.g. Bash(git diff:*)"))

    if spec:
        for key, kind in SPEC_FIELDS.items():
            if not isinstance(spec.get(key), kind):
                issues.append(("error", "bad-spec", f"spec.json {key!r} must be a {kind.__name__}"))
        if isinstance(spec.get("version"), str) and not SEMVER_RE.match(spec["version"]):
            issues.append(("error", "bad-spec", "spec.json version must be MAJOR.MINOR.PATCH"))
        files = [str(p.relative_to(skill.path)) for p in skill.path.rglob("*") if p.is_file()]
        for pattern in spec.get("fixable_files") or []:
            if ".." in pattern or pattern.startswith("/"):
                issues.append(("error", "bad-spec", f"fixable_files {pattern!r} escapes the skill dir"))
            elif not any(fnmatch.fnmatch(f, pattern) for f in files):
                issues.append(("error", "bad-spec", f"fixable_files {pattern!r} matches nothing"))
        for p in skill.evals_dir.rglob("*"):
            if p.is_symlink():
                issues.append(("error", "symlink", f"{p.relative_to(skill.evals_dir)} is a symlink; fixtures must be real files"))
        if not list((skill.evals_dir / "cases" / "regression").glob("*.json")):
            issues.append(("error", "no-regression-cases", f"evals/{skill.name}/cases/regression is empty"))

    # Broken references and committed secrets in every skill file.
    for f in sorted(skill.path.rglob("*")):
        if not f.is_file() or f.suffix not in (".md", ".json", ".sh", ".py"):
            continue
        text = f.read_text(errors="replace")
        rel = f.relative_to(skill.path)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                issues.append(("error", "secret", f"{rel}: matches secret pattern {pattern.pattern!r}"))
        if f.suffix == ".md":
            refs = set(REF_RE.findall(text)) | {r for r in LINK_RE.findall(text) if "://" not in r}
            for ref in sorted(refs):
                if not _resolve_ref(ref, skill):
                    issues.append(("error", "broken-reference", f"{rel}: reference {ref!r} does not exist"))
    return issues
