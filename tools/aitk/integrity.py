"""Criteria integrity: files under evals/ are append-only.

Between a base ref and the working tree, existing files under evals/ may not be modified
or deleted. New files are always fine. Two exceptions:
  - Promotion: an adversarial case moves, unchanged, to regression/ (a fixed weakness
    becomes a merge gate).
  - Version bump: evals/<skill>/spec.json may change its `version` field and nothing else.
Anything else needs the `criteria-change-approved` label plus code-owner review, which CI
passes in as --allow-criteria-change.

The weekly hardening workflow enforces the same rules in plain git and jq (its write-token
job must not run repo code). Keep both in step; tests/shell/test_harden_guard.sh covers that copy.
"""

import json
import re

from aitk.util import REPO_ROOT, git

ADV_RE = re.compile(r"^evals/([^/]+)/cases/adversarial/([^/]+\.json)$")
SPEC_RE = re.compile(r"^evals/[^/]+/spec\.json$")


def _show(ref, path, root):
    try:
        return git("show", f"{ref}:{path}", cwd=root)
    except RuntimeError:
        return None


def _semver(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return ()


def changed_files(base, root=REPO_ROOT):
    """(status, path) for evals/ changes between base and the working tree, incl. untracked."""
    out = git("diff", "--name-status", "--no-renames", base, "--", "evals/", cwd=root)
    changes = [tuple(line.split("\t", 1)) for line in out.splitlines() if line]
    untracked = git("ls-files", "--others", "--exclude-standard", "--", "evals/", cwd=root)
    return changes + [("A", p) for p in untracked.splitlines() if p]


def check(base, root=REPO_ROOT):
    """Return (violations, notes)."""
    violations, notes = [], []
    for status, path in changed_files(base, root):
        if status == "A":
            notes.append(f"added {path}")
            continue
        if status == "D":
            m = ADV_RE.match(path)
            promoted = root / f"evals/{m.group(1)}/cases/regression/{m.group(2)}" if m else None
            if promoted and promoted.exists() and promoted.read_text().strip() == (_show(base, path, root) or "").strip():
                notes.append(f"promoted {path} to regression")
            else:
                violations.append(f"{path}: deleted")
            continue
        if SPEC_RE.match(path):
            try:
                old = json.loads(_show(base, path, root) or "{}")
                new = json.loads((root / path).read_text())
            except json.JSONDecodeError as e:
                violations.append(f"{path}: unparseable JSON ({e})")
                continue
            changed = sorted(k for k in set(old) | set(new) if k != "version" and old.get(k) != new.get(k))
            if changed:
                violations.append(f"{path}: changed {changed} (only version may change)")
            elif _semver(new.get("version")) <= _semver(old.get("version")):
                violations.append(f"{path}: version must increase ({old.get('version')} -> {new.get('version')})")
            else:
                notes.append(f"{path}: version {old.get('version')} -> {new.get('version')}")
            continue
        violations.append(f"{path}: modified")
    return violations, notes
