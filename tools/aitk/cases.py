"""Eval case loading and schema validation.

Case sets (evals/<skill>/cases/<set>/<id>.json):
  regression   behavior that must keep working. Gates merges.
  adversarial  attacks and known open weaknesses. Reported, never gating.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

SETS = ("regression", "adversarial")
SEVERITIES = ("low", "medium", "high", "critical")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REQUIRED = ("id", "category", "description", "input", "expected_behavior", "assertions")
OPTIONAL = ("severity", "system_files", "tools", "permission_mode", "repeat", "mock")
# Assertion type -> keys it needs.
ASSERTION_KEYS = {
    "regex": ("pattern",), "not_regex": ("pattern",), "contract": (),
    "severity_at_least": ("near", "level"), "severity_at_most": ("near", "level"),
    "max_matches": ("pattern", "max"), "only_reference_files": ("allowed",),
    "no_tool_calls": ("tools",), "no_dangerous_actions": (), "rubric": ("criteria",),
}


@dataclass
class Case:
    data: dict
    set: str
    path: Path
    evals_dir: Path  # evals/<skill>/, for fixture paths

    def __getattr__(self, key):
        try:
            return self.data[key]
        except KeyError:
            raise AttributeError(key)

    @property
    def system_files(self):
        return self.data.get("system_files", ["SKILL.md"])

    def _inside(self, rel):
        path = (self.evals_dir / rel).resolve()
        if self.evals_dir.resolve() not in path.parents:
            raise ValueError(f"{rel!r} escapes {self.evals_dir}")
        return path

    def prompt(self):
        """The user prompt. {fixture} inlines a file; a {workspace} fixture is copied into
        the sandbox as the working directory instead of being inlined."""
        rel = self.input.get("fixture")
        text = self.input.get("prompt", "{fixture}")
        text = text.replace("{fixture}", self._inside(rel).read_text() if rel else "")
        return text.replace("{workspace}", "(The project is the current working directory.)")

    def workspace(self):
        rel = self.input.get("workspace")
        return self._inside(rel) if rel else None


def validate_case(data, path, categories, contracts=(), permission_modes=("default",)):
    errors = []
    for key in REQUIRED:
        if key not in data:
            errors.append(f"missing {key!r}")
    for key in data:
        if key not in REQUIRED + OPTIONAL:
            errors.append(f"unknown field {key!r}")
    cid = data.get("id", "")
    if cid and (not ID_RE.match(cid) or cid != path.stem):
        errors.append(f"id {cid!r} must be lowercase-hyphenated and match filename {path.stem!r}")
    if data.get("category") and data["category"] not in ("functional", *categories):
        errors.append(f"category {data['category']!r} is not 'functional' or in spec.json categories")
    if data.get("severity") and data["severity"] not in SEVERITIES:
        errors.append(f"severity must be one of {SEVERITIES}")
    if not data.get("assertions"):
        errors.append("at least one assertion is required")
    if data.get("permission_mode", "default") not in permission_modes:
        errors.append(f"permission_mode must be one of {list(permission_modes)}")
    for a in data.get("assertions", []):
        kind = a.get("type")
        if kind not in ASSERTION_KEYS:
            errors.append(f"unknown assertion type {kind!r}")
            continue
        for key in ASSERTION_KEYS[kind]:
            if not a.get(key) and a.get(key) != 0:
                errors.append(f"{kind} assertion needs {key!r}")
        for key in ("pattern", "near"):
            if key in a:
                try:
                    re.compile(a[key])
                except re.error as e:
                    errors.append(f"bad regex {a[key]!r}: {e}")
        if "level" in a and str(a["level"]).lower() not in SEVERITIES:
            errors.append(f"level must be one of {SEVERITIES}")
        if kind == "contract" and a.get("name", "default") not in contracts:
            errors.append(f"contract {a.get('name', 'default')!r} is not in spec.json output_contracts")
    return errors


def load_cases(skill, sets, permission_modes=("default",)):
    """Return (cases, errors) for a loaded Skill. Errors are schema problems (static failures)."""
    cases, errors = [], []
    categories = skill.spec.get("categories") or []
    for case_set in sets:
        for path in sorted((skill.evals_dir / "cases" / case_set).glob("*.json")):
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"{path.name}: invalid JSON: {e}")
                continue
            problems = validate_case(data, path, categories, skill.spec.get("output_contracts") or {},
                                     permission_modes)
            if problems:
                errors.extend(f"{path.name}: {p}" for p in problems)
                continue
            cases.append(Case(data, case_set, path, skill.evals_dir))
    return cases, errors
