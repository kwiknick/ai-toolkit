"""Shared helpers: repo paths, config, git, redaction, frontmatter parsing."""

import datetime
import json
import os
import re
import secrets
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG = {
    "provider": "claude-code",
    "model": None,          # None = the claude CLI's default model
    "judge_model": None,    # None = same as model; set a different one to avoid self-grading
    "max_model_calls": 40,  # per eval run, judge calls included
    "max_usd": 5.0,         # per eval run, judge calls included
    "call_max_usd": 1.0,    # per claude -p call (--max-budget-usd)
    "call_timeout_s": 300,
    "repeat": 1,
    "results_dir": ".aitk/results",
}

ENV_OVERRIDES = {
    "AITK_PROVIDER": ("provider", str),
    "AITK_MODEL": ("model", str),
    "AITK_JUDGE_MODEL": ("judge_model", str),
    "AITK_MAX_MODEL_CALLS": ("max_model_calls", int),
    "AITK_MAX_USD": ("max_usd", float),
    "AITK_CALL_TIMEOUT_S": ("call_timeout_s", int),
}

# Env vars whose values must never appear in results or evidence.
SECRET_ENV_VARS = ("ANTHROPIC_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "AITK_PR_TOKEN")

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


class ConfigError(Exception):
    """Bad flags, config, or missing tools (exit code 2)."""


def load_config(overrides=None, root=REPO_ROOT):
    """Defaults, then aitk.config.json, then AITK_* env vars, then CLI flags."""
    cfg = dict(DEFAULT_CONFIG)
    path = root / "aitk.config.json"
    if path.exists():
        cfg.update(json.loads(path.read_text()))
    for env, (key, cast) in ENV_OVERRIDES.items():
        if os.environ.get(env):
            try:
                cfg[key] = cast(os.environ[env])
            except ValueError as e:
                raise ConfigError(f"{env}: {e}")
    for key, value in (overrides or {}).items():
        if value is not None:
            cfg[key] = value
    return cfg


def redact(text):
    if not text:
        return text
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name)
        if value and len(value) >= 8:
            text = text.replace(value, f"[REDACTED:{name}]")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def git(*args, cwd=REPO_ROOT, check=True):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def git_commit(cwd=REPO_ROOT):
    try:
        return git("rev-parse", "HEAD", cwd=cwd)
    except RuntimeError:
        return None


def git_dirty(cwd=REPO_ROOT):
    try:
        return bool(git("status", "--porcelain", cwd=cwd))
    except RuntimeError:
        return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def new_run_id():
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


def parse_frontmatter(text):
    """Parse the simple `key: value` YAML subset used in SKILL.md frontmatter.

    Returns (fields, body). Raises ValueError when frontmatter is missing.
    """
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter (file must start with '---')")
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("unterminated frontmatter")
    fields = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t-":
            continue  # nested YAML is not used by our skills; ignore continuation lines
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"bad frontmatter line: {line!r}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        fields[key.strip()] = value
    return fields, text[end + 4:].lstrip("\n")
