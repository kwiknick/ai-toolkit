"""Model providers.

claude-code  Real model. Runs headless `claude -p` in a throwaway sandbox directory with
             the skill appended to the system prompt, and records every tool call.
             Works with an API key, a logged-in CLI, or Bedrock (CLAUDE_CODE_USE_BEDROCK=1).
mock         Canned responses from a case's `mock` block. Only the harness's own tests use it.
"""

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

from aitk.util import ConfigError

class ProviderError(Exception):
    """A model call failed (auth, timeout, CLI error). Exit code 2."""


class BudgetExceeded(ProviderError):
    pass


@dataclass
class Response:
    text: str
    provider: str
    model: str
    mocked: bool
    tool_calls: list = field(default_factory=list)
    supports_tools: bool = False
    cost_usd: float = None


@dataclass
class Request:
    system: str
    prompt: str
    case: object = None   # Case, for mock responses and the workspace fixture
    tools: list = None    # None = no tools; list = exactly these tools
    permission_mode: str = None


class Budget:
    """Caps model calls and dollars for one eval run. Checked before every call."""

    def __init__(self, max_calls, max_usd):
        self.max_calls, self.max_usd = max_calls, max_usd
        self.calls, self.usd = 0, 0.0

    def charge(self):
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"model-call budget exhausted ({self.max_calls} calls)")
        if self.usd >= self.max_usd:
            raise BudgetExceeded(f"dollar budget exhausted (${self.usd:.2f} of ${self.max_usd:.2f})")
        self.calls += 1

    def spend(self, usd):
        self.usd += usd or 0.0


class MockProvider:
    name, mocked = "mock", True

    def __init__(self, cfg, budget, model=None):
        self.model, self.budget = "mock", budget

    def complete(self, req):
        self.budget.charge()
        mock = (req.case.data.get("mock") if req.case else None) or {}
        chosen = mock.get("default")
        for option in mock.get("responses", []):
            if option["when_system_contains"] in req.system:
                chosen = option
                break
        if chosen is None:
            raise ProviderError("case has no mock response")
        return Response(chosen["text"], "mock", "mock", True, chosen.get("tool_calls", []),
                        supports_tools="tool_calls" in chosen)


class ClaudeCodeProvider:
    name, mocked = "claude-code", False

    def __init__(self, cfg, budget, model=None):
        self.cfg, self.budget = cfg, budget
        self.model = model if model is not None else cfg.get("model")
        if not shutil.which("claude"):
            raise ConfigError("the claude CLI is not on PATH (install Claude Code)")

    def complete(self, req):
        self.budget.charge()
        sandbox = tempfile.mkdtemp(prefix="aitk-sandbox-")
        try:
            workspace = req.case.workspace() if req.case else None
            if workspace:
                shutil.copytree(workspace, sandbox, dirs_exist_ok=True, symlinks=True)
                # Make it look like a real project: a git repo with one commit.
                env = dict(os.environ, GIT_AUTHOR_NAME="aitk", GIT_AUTHOR_EMAIL="aitk@example.invalid",
                           GIT_COMMITTER_NAME="aitk", GIT_COMMITTER_EMAIL="aitk@example.invalid")
                for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "fixture"]):
                    subprocess.run(["git", *args], cwd=sandbox, env=env, capture_output=True)
            cmd = ["claude", "-p", req.prompt,
                   "--append-system-prompt", req.system,
                   "--output-format", "stream-json", "--verbose",
                   "--no-session-persistence", "--disable-slash-commands",
                   # Isolate from the user's MCP servers, hooks, and settings.
                   "--strict-mcp-config", "--setting-sources", "project",
                   "--permission-mode", req.permission_mode or "default",
                   "--tools", ",".join(req.tools or []),
                   "--max-budget-usd", str(self.cfg["call_max_usd"])]
            if self.model:
                cmd += ["--model", self.model]
            try:
                result = subprocess.run(cmd, cwd=sandbox, capture_output=True, text=True,
                                        timeout=self.cfg["call_timeout_s"], stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                self.budget.spend(self.cfg["call_max_usd"])  # unknown spend: assume the per-call cap
                raise ProviderError(f"claude -p timed out after {self.cfg['call_timeout_s']}s")
            text, tool_calls, cost, is_error = "", [], None, False
            for line in result.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "assistant":
                    for block in event.get("message", {}).get("content", []):
                        if block.get("type") == "tool_use":
                            tool_calls.append({"name": block.get("name"), "input": block.get("input")})
                elif event.get("type") == "result":
                    text = event.get("result") or ""
                    cost = event.get("total_cost_usd")
                    is_error = event.get("is_error", False)
            self.budget.spend(cost)
            if is_error or (not text and result.returncode != 0):
                # An error result (overload, budget, auth) is infra, never a skill answer to grade.
                tail = (text or result.stderr.strip() or result.stdout.strip())[-400:]
                raise ProviderError(f"claude -p error (exit {result.returncode}): {tail}")
            return Response(text, self.name, self.model or "cli-default", False, tool_calls,
                            supports_tools=True, cost_usd=cost)
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)


_CLASSES = {"claude-code": ClaudeCodeProvider, "mock": MockProvider}
PROVIDERS = tuple(_CLASSES)


def make(name, cfg, budget, model=None):
    if name not in _CLASSES:
        raise ConfigError(f"unknown provider {name!r}; choose from {PROVIDERS}")
    return _CLASSES[name](cfg, budget, model)
